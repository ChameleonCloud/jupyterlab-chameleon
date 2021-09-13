# Copyright 2021 University of Chicago
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from contextlib import contextmanager
import io
import ipaddress
import json
import logging
import os
import pathlib
import shlex
import subprocess
import sys
import tempfile
import typing

import ansible_runner
from jupyter_client.connect import port_names, tunnel_to_kernel
from jupyter_client.kernelspec import KernelSpecManager, NoSuchKernel
from paramiko.client import AutoAddPolicy, RejectPolicy, SSHClient
from paramiko.ssh_exception import NoValidConnectionsError, SSHException
from scp import SCPClient
from traitlets.traitlets import Bool

from ..binding import Binding, BindingConnectionError
from ..utils import redirect_output
from .base import HydraKernelManager, KernelProxy

LOG = logging.getLogger(__name__)
DEFAULT_SSH_TIMEOUT = 10


class SSHConnection(object):
    def __init__(self, binding: "Binding"):
        self.binding = binding

    def exec(
        self, command: "typing.Union[list,str]", timeout=None
    ) -> "tuple[int,io.RawIOBase,io.RawIOBase]":
        """Execute a command on the binding host.

        The command is executed via a SSH session.

        Args:
            command (Union[list,str]): the command to run. This can either be
                passed as a list of command arguments, or as a command string.
            timeout (int): how long to wait before terminating the command.
                Defaults to None, meaning no timeout.

        Returns:
            tuple[int,RawIOBase,RawIOBase]: a tuple of the return code, and
                an IO stream for captured stdout and stderr, respectively.
        """
        if isinstance(command, str):
            command = shlex.split(command)
        with self._ssh_connect() as ssh:
            _, stdout, stderr = ssh.exec_command(shlex.join(command), timeout=timeout)
            return stdout.channel.recv_exit_status(), stdout, stderr

    def exec_json(self, command: "str", timeout=None) -> "typing.Union[dict,list]":
        code, stdout, stderr = self.exec(command, timeout=timeout)
        if code > 0:
            raise RuntimeError(stderr.read())
        return json.load(stdout)

    @contextmanager
    def get_file(self, path: "str") -> "io.BytesIO":
        with self._ssh_connect() as ssh:
            scp = SCPClient(ssh.get_transport())
            with tempfile.NamedTemporaryFile() as tmpf:
                scp.get(path, tmpf.name)
                tmpf.seek(0)
                yield tmpf

    def _ssh_connect(self) -> "SSHClient":
        client = SSHClient()
        client.set_missing_host_key_policy(
            RejectPolicy if self.host_key_checking else AutoAddPolicy
        )
        binding_connection = self.binding.connection
        try:
            client.connect(
                binding_connection["host"],
                username=binding_connection.get("user"),
                key_filename=binding_connection.get("ssh_private_key_file"),
                timeout=binding_connection.get("ssh_timeout", DEFAULT_SSH_TIMEOUT),
            )
        except NoValidConnectionsError as exc:
            raise BindingConnectionError(binding_name=self.binding.name) from exc
        except SSHException as exc:
            raise BindingConnectionError(binding_name=self.binding.name) from exc
        return client


class SSHHydraKernelManager(HydraKernelManager):
    # Tell the multi-kernel manager NOT to cache the auto-assigned ports;
    # the kernel manager will override them after launching the subkernel.
    cache_ports = False

    host_key_checking = Bool(
        False,
        help=(
            "If set, remote connections to hosts that do not have an entry in the "
            "system host key list will raise an error."
        ),
    )

    tunnel = Bool(
        True,
        help=(
            "If set, connection to remote kernel will be established over an SSH "
            "tunnel. Remote kernels on loopback hosts will not have tunnels."
        ),
    )

    _virtualenv = None

    @property
    def virtualenv(self):
        if self._virtualenv is None:
            paths = SSHConnection(self.binding).exec_json("jupyter --paths --json")
            self._virtualenv = os.path.join(paths["data"][0], "hydra-kernel", "venv")
        return self._virtualenv

    def post_init(self, binding: "Binding"):
        self.kernel_spec_manager = SSHKernelSpecManager(binding=binding)
        binding.observe(self._on_binding_connection_changed, "connection")

    def _on_binding_connection_changed(self, change):
        # Invalidate cached value
        self._virtualenv = None
        self.kernel_spec_manager = SSHKernelSpecManager(binding=self.binding)

    def format_kernel_cmd(self, extra_arguments):
        cmd = super().format_kernel_cmd(extra_arguments=extra_arguments)
        cmd.append(f"--id={self.kernel_id}")
        venv_bin = os.path.join(self.virtualenv, "bin")
        cmd[0] = os.path.join(venv_bin, cmd[0])
        cmd.append(f"--launcher={os.path.join(venv_bin, 'hydra-subkernel')}")

        return cmd

    def _save_host_key(self, host):
        hosts_file_path = pathlib.Path(pathlib.Path.home(), ".ssh", "known_hosts")
        hosts_file_path.parent.mkdir(exist_ok=True)
        hosts_file_path.touch()
        with hosts_file_path.open("a") as hosts_file:
            with redirect_output() as stderr:
                proc = subprocess.run(
                    shlex.split(f"ssh-keyscan -H {host}"),
                    stdout=hosts_file,
                    stderr=stderr,
                )
                if proc.returncode != 0:
                    LOG.warning(
                        (
                            f"Failed to update host key for {host}: "
                            f"{proc.stderr.read()}"
                        )
                    )

    def _launch_kernel(self, kernel_cmd, **kw):
        # The connection file has already been written as part of `pre_start_kernel`,
        # but we are going to be overriding ports to the subkernel's exposed
        # ports (or ports exposed via a SSH tunnel).
        self.reset_ports()
        self.cleanup_connection_file()

        remote = SSHConnection(self.binding)

        LOG.info(f"{self.binding.name}: kernel_cmd={kernel_cmd}")
        subkernel = remote.exec_json(kernel_cmd)

        conn_info = subkernel["connection"]
        self.load_connection_info(conn_info)
        LOG.info(f"{self.binding.name}: connection={conn_info}")

        if self.tunnel:
            conn = self.binding.connection
            sshkey = conn.get("ssh_private_key_file")
            sshserver = f"{conn.get('user')}@{conn['host']}"

            if not self.host_key_checking:
                self._save_host_key(conn["host"])

            LOG.info(f"{self.binding.name}: tunneling to {sshserver}")

            (
                self.shell_port,
                self.iopub_port,
                self.stdin_port,
                self.hb_port,
                self.control_port,
            ) = tunnel_to_kernel(conn_info, sshserver, sshkey=sshkey)

        self.write_connection_file()

        return SSHKernelProxy(remote, subkernel["pid"])


class SSHKernelProxy(KernelProxy):
    def __init__(self, remote: "SSHConnection", pid):
        self.remote = remote
        self.pid = pid

    def send_signal(self, signum):
        try:
            code, _, _ = self.remote.exec(f"kill -{signum} {self.pid}")
        except BindingConnectionError as exc:
            LOG.error(f"Failed to send signal: {exc}")
            code = -1
        return code


class SSHKernelSpecManager(KernelSpecManager):
    """A kernel spec manager that provisions kernel specs on remote hosts.

    For supported kernels, an Ansible playbook is run against the remote host
    to install all dependencies for the kernel, and the kernel itself.

    To look up kernels, the manager connects via SSH to the host and inspects
    the default directories where kernelspecs are installed.
    """

    def __init__(self, binding: "Binding" = None, **kwargs):
        super().__init__(**kwargs)
        self.binding = binding
        self._kernelspecs = None
        self._kernelspec_info = {}

    def _invalidate_specs(self):
        self._kernelspecs = None
        self._kernelspec_info = {}

    def find_kernel_specs(self):
        if not self._kernelspecs:
            LOG.info(f"Fetching all kernel specs for '{self.binding.name}'")
            try:
                self._kernelspecs = self.exec_json("jupyter kernelspec list --json")[
                    "kernelspecs"
                ]
            except RuntimeError as exc:
                LOG.warn((f"Failed to list kernel specs on {self.binding.name}: {exc}"))

        kernelspecs = self._kernelspecs or {}

        return {name: spec["resource_dir"] for name, spec in kernelspecs.items()}

    def remove_kernel_spec(self, name):
        raise NotImplementedError("Removing remote specs not yet supported")

    def get_kernel_spec(self, kernel_name):
        resource_dir = self.find_kernel_specs().get(kernel_name)
        if not resource_dir:
            raise NoSuchKernel(kernel_name)

        if resource_dir not in self._kernelspec_info:
            info_path = os.path.join(resource_dir, "kernel.json")
            with self.get_file(info_path) as f:
                self._kernelspec_info[resource_dir] = spec_info = json.load(f)
                LOG.info(
                    (
                        f"Loaded {kernel_name} spec for {self.binding.name}: "
                        f"{spec_info}"
                    )
                )

        spec = self.kernel_spec_class(
            resource_dir=resource_dir, **self._kernelspec_info[resource_dir]
        )

        spec.argv = ["hydra-agent", f"--kernel={kernel_name}"]
        return spec

    def provision_kernel_spec(self, kernel_name, **kwargs):
        self._invalidate_specs()

        ansible_dir = os.path.join(sys.prefix, "share", "hydra-kernel", "ansible")
        host_vars = self._host_vars()

        with tempfile.TemporaryDirectory() as tmpdir:
            with redirect_output():
                runner = ansible_runner.run(
                    private_data_dir=tmpdir,
                    project_dir=ansible_dir,
                    inventory={"all": {"hosts": {"KERNEL": host_vars}}},
                    playbook="kernel_action.yml",
                    extravars={
                        "kernel_name": kernel_name,
                        "kernel_action": "install",
                    },
                    event_handler=self._on_ansible_event,
                    # Don't output to stdout, store as JSON instead
                    quiet=True,
                    json_mode=True,
                )
                LOG.info(runner.stdout.read())

    def _host_vars(self):
        conn = self.binding.connection
        host = conn["host"]
        host_vars = {
            "ansible_host": host,
            "ansible_user": conn.get("user"),
            "ansible_become": conn.get("sudo", False),
            "ansible_ssh_private_key_file": conn.get("ssh_private_key_file"),
            # TODO: handle "via"
        }
        return host_vars

    def _on_ansible_event(self, event):
        LOG.debug(f"ansible event: {event}")
