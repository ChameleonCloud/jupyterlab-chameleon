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
import io
import json
import logging
import os
import pathlib
import shlex
import subprocess
import sys
import tempfile
import typing
from contextlib import contextmanager

import ansible_runner
from jupyter_client.connect import tunnel_to_kernel
from paramiko.client import AutoAddPolicy, RejectPolicy, SSHClient
from paramiko.ssh_exception import NoValidConnectionsError, SSHException
from scp import SCPClient
from traitlets.traitlets import Bool, Instance, Int, Unicode

from ..binding import BindingConnectionError
from ..utils import redirect_output
from .base import HydraKernelProvisioner

if typing.TYPE_CHECKING:
    from typing import Any, Dict, List

LOG = logging.getLogger(__name__)
DEFAULT_SSH_TIMEOUT = 10


class SSHHydraKernelProvisioner(HydraKernelProvisioner):
    host = Unicode()
    user = Unicode()
    private_key_file = Unicode()
    timeout = Int(DEFAULT_SSH_TIMEOUT)
    sudo = Bool(False)
    host_key_checking = Bool(
        False,
        help=(
            "If set, remote connections to hosts that do not have an entry in the "
            "system host key list will raise an error."
        ),
    )

    connection = Instance(
        "hydra_kernel.provisioning.ssh.SSHConnection", allow_none=True
    )
    pid = Int(allow_none=True)

    _virtualenv = None
    _kernelspecs = None

    @property
    def has_process(self) -> bool:
        return self.connection is not None and self.pid is not None

    def reset(self) -> None:
        self.connection = None
        self.pid = None
        self._kernelspecs = None

    @property
    def virtualenv(self):
        if self._virtualenv is None:
            paths = SSHConnection(self.binding).exec_json("jupyter --paths --json")
            self._virtualenv = os.path.join(paths["data"][0], "hydra-kernel", "venv")
        return self._virtualenv

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

    async def pre_launch(self, **kwargs: "Any") -> "Dict[str, Any]":
        kwargs = await super().pre_launch(**kwargs)
        venv_bin = os.path.join(self.virtualenv, "bin")
        kwargs["cmd"] = [
            os.path.join(venv_bin, "hydra-agent"),
            f"--kernel={self.subkernel_name}",
            f"--id={self.kernel_id}",
            f"--launcher={os.path.join(venv_bin, 'hydra-subkernel')}",
        ]

        # Check if desired kernel exists on remote
        if not await self.has_remote_kernelspec(self.subkernel_name):
            await self.provision_remote_kernelspec(self.subkernel_name)

        return kwargs

    async def launch_kernel(self, command, **kwargs):
        if not self.host_key_checking:
            self._save_host_key(self.host)

        self.connection = SSHConnection(parent=self)

        LOG.info(f"{self.binding.name}: kernel_cmd={command}")
        subkernel = self.connection.exec_json(command)
        conn_info = subkernel["connection"]
        LOG.info(f"{self.binding.name}: connection={conn_info}")

        sshserver = f"{self.user}@{self.host}"
        LOG.info(f"{self.binding.name}: tunneling to {sshserver}")
        (
            shell_port,
            iopub_port,
            stdin_port,
            hb_port,
            control_port,
        ) = tunnel_to_kernel(conn_info, sshserver, sshkey=self.private_key_file)

        conn_info["ip"] = "127.0.0.1"
        conn_info["shell_port"] = shell_port
        conn_info["iopub_port"] = iopub_port
        conn_info["stdin_port"] = stdin_port
        conn_info["hb_port"] = hb_port
        conn_info["control_port"] = control_port

        self.pid = int(subkernel["pid"])

        return conn_info

    async def send_signal(self, signum):
        try:
            self.connection.exec(f"kill -{signum} {self.pid}")
        except BindingConnectionError as exc:
            LOG.error(f"Failed to send signal: {exc}")

    async def has_remote_kernelspec(self, kernel_name):
        if not self._kernelspecs:
            LOG.info(f"Fetching all kernel specs for '{self.binding.name}'")
            try:
                self._kernelspecs = self.connection.exec_json(
                    "jupyter kernelspec list --json"
                )["kernelspecs"]
            except RuntimeError as exc:
                LOG.warn((f"Failed to list kernel specs on {self.binding.name}: {exc}"))

        # TODO: also check languages?
        return kernel_name in self._kernelspecs

    async def provision_remote_kernelspec(self, kernel_name):
        ansible_dir = os.path.join(sys.prefix, "share", "hydra-kernel", "ansible")
        host_vars = {
            "ansible_host": self.host,
            "ansible_user": self.user,
            "ansible_become": self.sudo,
            "ansible_ssh_private_key_file": self.private_key_file,
            # TODO: handle "via"
        }

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

        # Invalidate kernelspecs as we have installed a new one
        self._kernelspecs = None

    def _on_ansible_event(self, event):
        LOG.debug(f"ansible event: {event}")


class SSHConnection(object):
    def __init__(self, parent: "SSHHydraKernelProvisioner"):
        self.parent = parent

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
        parent = self.parent
        client = SSHClient()
        client.set_missing_host_key_policy(
            RejectPolicy if parent.host_key_checking else AutoAddPolicy
        )
        try:
            client.connect(
                parent.host,
                username=parent.user,
                key_filename=parent.private_key_file,
                timeout=parent.timeout,
            )
        except NoValidConnectionsError as exc:
            raise BindingConnectionError(binding_name=parent.binding.name) from exc
        except SSHException as exc:
            raise BindingConnectionError(binding_name=parent.binding.name) from exc
        return client
