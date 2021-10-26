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
import asyncio
import io
import json
import logging
import math
import os
import pathlib
import re
import shlex
import sys
import tarfile
import tempfile
import typing
import uuid
from contextlib import contextmanager, redirect_stdout

import ansible_runner
from jupyter_client.connect import port_names
from jupyter_client.ssh.tunnel import select_random_ports
from paramiko.client import AutoAddPolicy, RejectPolicy, SSHClient
from paramiko.ssh_exception import NoValidConnectionsError, SSHException
from scp import SCPClient
from traitlets.traitlets import Bool, Instance, Int, Unicode

from ..binding import BindingConnectionError
from .base import FileManagementMixin, HydraKernelProvisioner

if typing.TYPE_CHECKING:
    from jupyter_client.connect import KernelConnectionInfo
    from typing import Any, Dict, List, Optional, Tuple

LOG = logging.getLogger(__name__)
DEFAULT_SSH_TIMEOUT = 10


def _expand_path(path):
    if not path:
        return None
    return str(pathlib.Path(path).expanduser().resolve())


class SSHHydraKernelProvisioner(FileManagementMixin, HydraKernelProvisioner):
    host = Unicode()
    user = Unicode()
    private_key_file = Unicode(allow_none=True)
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

    _kernelspecs: "Dict" = None
    _subkernel_connection: "KernelConnectionInfo" = None
    _tunnels: "Dict[str, Tuple[str, int]]" = {}
    _tunnel_ctl_path: "str" = None

    @property
    def has_process(self) -> bool:
        if self.connection is None:
            return False
        if self.pid is None:
            return False
        return True

    def reset(self) -> None:
        self.connection = None
        self.pid = None
        self._kernelspecs = None
        self._tunnels = {}
        self._tunnel_ctl_path = None

    async def _save_host_key(self):
        hosts_file_path = pathlib.Path(pathlib.Path.home(), ".ssh", "known_hosts")
        hosts_file_path.parent.mkdir(exist_ok=True)
        hosts_file_path.touch()
        with hosts_file_path.open("r+") as hosts_file:
            start = f"# BEGIN hydra_kernel: {self.host}"
            end = f"# END hydra_kernel: {self.host}"
            lines = hosts_file.readlines()
            start_i, end_i = 0, 0
            for i, line in enumerate(lines):
                if line == start:
                    start_i = i
                elif line == end:
                    end_i = i
                    break
            # Splice out block
            lines = lines[:start_i] + lines[end_i:]

            proc = await asyncio.create_subprocess_exec(
                "ssh-keyscan",
                "-H",
                shlex.quote(self.host),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                LOG.warning(
                    (f"Failed to update host key for {self.host}: {stderr.read()}")
                )

            lines.append(start)
            lines.append(stdout.decode("utf-8"))
            lines.append(end)
            hosts_file.seek(0)
            hosts_file.write("\n".join(lines))

    async def pre_launch(self, **kwargs: "Any") -> "Dict[str, Any]":
        kwargs = await super().pre_launch(**kwargs)

        self.connection = SSHConnection(parent=self)

        # Check if desired kernel exists on remote
        self.binding.update_progress("Checking host kernels")
        if not await self.has_hydra_kernelspec(self.subkernel_name):
            self.binding.update_progress(f"Installing {self.subkernel_name} kernel")
            await self.provision_hydra_kernelspec(self.subkernel_name)

        kwargs["cmd"] = [
            "hydra-agent",
            f"--kernel={self.subkernel_name}",
            f"--id={self.kernel_id}",
            f"--launcher=hydra-subkernel",
        ]

        return kwargs

    async def launch_kernel(self, command, **kwargs):
        self.binding.update_progress("Establishing secure connection")

        LOG.debug(f"{self.binding.name}: kernel_cmd={command}")
        subkernel = self.connection.exec_json(command, login=True)
        self._subkernel_connection = subkernel["connection"]
        LOG.debug(f"{self.binding.name}: connection={self._subkernel_connection}")

        conn_info = self._subkernel_connection.copy()

        if not self.host_key_checking:
            await self._save_host_key()

        for port_name in port_names:
            conn_info[port_name] = await self._tunnel_to_port(port_name)

        self.pid = int(subkernel["pid"])

        return conn_info

    async def send_signal(self, signum):
        try:
            self.connection.exec(f"kill -{signum} {self.pid}")
        except BindingConnectionError as exc:
            LOG.error(f"Failed to send signal: {exc}")

    async def poll(self) -> "Optional[int]":
        try:
            # TODO: also check status of tunnels here
            self.connection.exec(f"kill -0 {self.pid}")
        except OSError:
            return -1

    async def cleanup(self, restart: bool = False) -> None:
        for port_name, tunnel in self._tunnels.items():
            try:
                LOG.debug(f"Killing {port_name} SSH tunnel (pid={tunnel['pid']})")
                os.kill(tunnel["pid"])
            except OSError:
                pass
        self._tunnels = {}

    async def has_hydra_kernelspec(self, kernel_name):
        try:
            ret, _, _ = self.connection.exec("which hydra-subkernel")
            if ret != 0:
                return False
        except RuntimeError as exc:
            LOG.error(
                f"Failed to check for hydra binaries on {self.binding_name}: {exc}"
            )
            return False

        if not self._kernelspecs:
            LOG.info(f"Fetching all kernel specs for '{self.binding.name}'")
            try:
                self._kernelspecs = self.connection.exec_json(
                    "jupyter kernelspec list --json --log-level ERROR", login=True
                )["kernelspecs"]
            except RuntimeError as exc:
                LOG.warn(f"Failed to list kernel specs on {self.binding.name}: {exc}")
                return False

        for spec_name, spec_info in self._kernelspecs.items():
            lang = spec_info["spec"]["language"]
            if spec_name == kernel_name or lang == kernel_name:
                return True

        return False

    async def provision_hydra_kernelspec(self, kernel_name):
        ansible_dir = os.path.join(sys.prefix, "share", "hydra-kernel", "ansible")
        host_vars = {
            "ansible_host": self.host,
            "ansible_user": self.user,
            "ansible_become": self.sudo,
            "ansible_ssh_private_key_file": _expand_path(self.private_key_file),
            # TODO: handle "via"
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with redirect_stdout(io.StringIO()):
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
                LOG.debug(runner.stdout.read())
                if runner.status != "successful" or runner.errored:
                    raise RuntimeError(f"Failed to install kernel {kernel_name}")

        # Invalidate kernelspecs as we have installed a new one
        self._kernelspecs = None

    async def upload_path(self, local_path: "str", remote_path: "str" = None):
        req_id = uuid.uuid4()
        tmp_archive = f"/tmp/{req_id}.tar.gz"

        self.binding.update_progress("Preparing upload")
        fd = self.prepare_upload(local_path)

        def _on_progress(filename, size, sent):
            self.binding.update_progress(
                f"Uploading ({math.floor((sent/size) * 100)}%)"
            )

        self.connection.put_file(fd, tmp_archive, on_progress=_on_progress)

        self.binding.update_progress("Finishing")
        self.connection.exec(["tar", "xzf", tmp_archive, "-C", remote_path])
        self.connection.exec(["rm", "-f", tmp_archive])

    async def download_path(self, remote_path: "str", local_path: "str" = None):
        req_id = uuid.uuid4()
        tmp_archive = f"/tmp/{req_id}.tar.gz"

        self.binding.update_progress("Preparing download")
        self.connection.exec(["tar", "czf", tmp_archive, "-C", remote_path, "."])

        def _on_progress(filename, size, sent):
            self.binding.update_progress(
                f"Downloading ({math.floor((sent/size) * 100)}%)"
            )

        with self.connection.get_file(
            tmp_archive, on_progress=_on_progress
        ) as archive_fd:
            self.binding.update_progress("Finishing")
            with tarfile.open(fileobj=archive_fd, mode="r") as tar:
                tar.extractall(local_path)
        self.connection.exec(["rm", "-f", tmp_archive])

    async def _tunnel_to_port(self, port_name: "str", lport: "int" = None) -> "int":
        stream = io.StringIO()
        error = None

        with redirect_stdout(stream):
            try:
                subkernel_conn = self._subkernel_connection
                self.binding.update_progress(f"Starting kernel {port_name} tunnel")
                if not await self._is_tunnel_up():
                    await self._start_tunnel()
                if not lport:
                    lport = select_random_ports(1)[0]
                await self._forward_over_tunnel(lport, subkernel_conn[port_name])
                self._tunnels[port_name] = lport
            except (RuntimeError, TypeError) as exc:
                error = exc

        if error:
            stream.seek(0)
            LOG.error(f"error={error}, stdout={stream.read()}")
            raise RuntimeError(f"Failed to establish tunnel for {port_name}: {error}")

        return self._tunnels[port_name]

    @property
    def _ssh_host(self):
        return f"{self.user}@{self.host}"

    @property
    def _ssh_cmd(self):
        cmd = ["ssh"]
        if self.private_key_file:
            cmd.extend(["-i", _expand_path(self.private_key_file)])
        return cmd

    async def _start_tunnel(self):
        self._tunnel_ctl_path = pathlib.Path(
            tempfile.gettempdir(), f"{self.user}-{self.host.replace('.', '-')}.tunnel"
        )
        if self._tunnel_ctl_path.exists():
            self._tunnel_ctl_path.unlink()

        cmd = self._ssh_cmd
        cmd.extend(
            [
                "-fN",  # -f = background process, -N = don't run a command
                "-o",
                "ControlMaster=yes",
                "-o",
                f"ControlPath={self._tunnel_ctl_path}",
                "-o",
                "ServerAliveInterval=5",
                self._ssh_host,
            ]
        )
        tunnel_proc = await asyncio.create_subprocess_exec(*cmd)
        _, stderr = await tunnel_proc.communicate()
        if tunnel_proc.returncode != 0:
            try:
                self._tunnel_ctl_path = None
            except:
                pass
            raise RuntimeError(f"Failed to establish SSH tunnel to {self.host}")

    async def _forward_over_tunnel(self, lport, rport):
        LOG.debug(f"_forward_over_tunnel: forwarding {lport} => {rport}")
        returncode, _, _ = await self._tunnel_command(
            ["forward", "-L", f"127.0.0.1:{lport}:127.0.0.1:{rport}"]
        )

    async def _is_tunnel_up(self):
        if not self._tunnel_ctl_path:
            return False
        returncode, _, _ = await self._tunnel_command(["check"])
        return returncode == 0

    async def _tunnel_command(self, cmd: "list[str]"):
        proc = await asyncio.create_subprocess_exec(
            *self._ssh_cmd,
            "-o",
            f"ControlPath={self._tunnel_ctl_path}",
            "-O",
            *cmd,
            self._ssh_host,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout, stderr

    def _on_ansible_event(self, event):
        current_task = event.get("event_data", {}).get("task")
        if current_task:
            self.binding.update_progress(current_task)


class SSHConnection(object):
    def __init__(self, parent: "SSHHydraKernelProvisioner"):
        self.parent = parent

    def exec(
        self, command: "typing.Union[list,str]", login=False, timeout=None
    ) -> "tuple[int,io.RawIOBase,io.RawIOBase]":
        """Execute a command on the binding host.

        The command is executed via a SSH session.

        Args:
            command (Union[list,str]): the command to run. This can either be
                passed as a list of command arguments, or as a command string.
            login (bool): whether to invoke a login shell. This is more brittle
                and complex than opening a non-interactive/login session, so
                should only be used if having a "real" user environment is
                necessary.
            timeout (int): how long to wait before terminating the command.
                Defaults to None, meaning no timeout.

        Returns:
            tuple[int,RawIOBase,RawIOBase]: a tuple of the return code, and
                an IO stream for captured stdout and stderr, respectively.
        """
        if isinstance(command, str):
            command = shlex.split(command)

        safe_cmd = shlex.join(command)

        with self._ssh_connect() as ssh:
            if login:
                return self._exec_login_shell(ssh, safe_cmd, timeout=timeout)
            else:
                _, stdout, stderr = ssh.exec_command(safe_cmd, timeout=timeout)
                return stdout.channel.recv_exit_status(), stdout, stderr

    def _exec_login_shell(
        self, ssh: "SSHClient", safe_cmd: "str", timeout: "float" = None
    ) -> "tuple[int,io.StringIO,io.StringIO]":
        chan = ssh.invoke_shell()
        chan.settimeout(timeout)
        stdout = ""
        stderr = ""
        start_cmd = "echo ::start"
        exit_cmd = "echo ::exit=$?"
        # Prefix the command w/ the start command; this is because sometimes
        # the TTY will echo parts of lagging inputs to stdout multiple times,
        # and this can cause problems. echo will put "::start" on its own line,
        # which is a more reliable token to use to tell when to start parsing
        # the command output.
        commands = [f"{start_cmd} && {safe_cmd}", exit_cmd]
        chan.sendall("\n".join(commands) + "\n")
        exit_status = 0
        while True:
            if chan.recv_stderr_ready():
                stderr += chan.recv_stderr(4096).decode("utf-8")
            if chan.recv_ready():
                sout = chan.recv(4096).decode("utf-8")
                stdout += sout
                if re.search("::exit=(\d+)", sout):
                    break

        proc_stdout = []
        in_proc_out = False
        for line in stdout.splitlines():
            if in_proc_out:
                if exit_cmd in line:
                    continue
                if line.startswith("::exit"):
                    exit_status = int(line.split("=")[1])
                    break
                proc_stdout.append(line)
            elif line == "::start":
                # When paramiko runs the command it will often flush it
                # to the buffer before the shell has the chance to start
                # executing it; the shell will print the command again as
                # part of the prompt. By ignoring a single line that is
                # the entire contents of the command we can edit out this
                # case.
                in_proc_out = True

        chan.close()
        return (
            exit_status,
            io.StringIO("\n".join(proc_stdout)),
            io.StringIO(stderr),
        )

    def exec_json(
        self, command: "str", login=False, timeout=None
    ) -> "typing.Union[dict,list]":
        code, stdout, stderr = self.exec(command, login=login, timeout=timeout)
        if code > 0:
            raise RuntimeError(stderr.read())
        return json.load(stdout)

    @contextmanager
    def get_file(self, path: "str", on_progress=None) -> "io.BytesIO":
        with self._ssh_connect() as ssh:
            scp = SCPClient(ssh.get_transport(), progress=on_progress)
            with tempfile.NamedTemporaryFile() as tmpf:
                scp.get(path, tmpf.name)
                tmpf.seek(0)
                yield tmpf

    def put_file(self, fileobj: "io.BytesIO", path: "str", on_progress=None):
        with self._ssh_connect() as ssh:
            scp = SCPClient(ssh.get_transport(), progress=on_progress)
            scp.putfo(fileobj, path)

    def _ssh_connect(self) -> "SSHClient":
        parent = self.parent
        client = SSHClient()
        client.set_missing_host_key_policy(
            RejectPolicy if parent.host_key_checking else AutoAddPolicy
        )
        try:
            LOG.debug(
                f"connecting, host={parent.host}, user={parent.user}, key={parent.private_key_file}"
            )
            client.connect(
                parent.host,
                username=parent.user,
                key_filename=_expand_path(parent.private_key_file),
                timeout=parent.timeout,
            )
        except NoValidConnectionsError as exc:
            raise BindingConnectionError(binding_name=parent.binding.name) from exc
        except SSHException as exc:
            raise BindingConnectionError(binding_name=parent.binding.name) from exc
        return client
