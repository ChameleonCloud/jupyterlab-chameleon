from contextlib import contextmanager
from hydra_kernel.exception import HydraException
import io
import ipaddress
import json
import logging
import os
import shlex
import subprocess
import tempfile
import typing

from paramiko.client import AutoAddPolicy, RejectPolicy, SSHClient
from paramiko.ssh_exception import NoValidConnectionsError, SSHException
from scp import SCPClient
from traitlets.traitlets import Bool, Enum, HasTraits, Dict, Unicode, observe


LOG = logging.getLogger(__name__)

DEFAULT_SSH_TIMEOUT = 10
DEFAULT_KERNEL = 'bash'
SUPPORTED_KERNELS = (
    'bash', 'python'
)


class BindingConnectionError(HydraException):
    _msg_fmt = "Could not connect to binding %(binding_name)"


class Binding(HasTraits):
    name = Unicode(read_only=True)
    kernel = Enum(SUPPORTED_KERNELS, default_value=DEFAULT_KERNEL)
    connection = Dict()

    host_key_checking = Bool(False, help=(
        "If set, remote connections to hosts that do not have an entry in the "
        "system host key list will raise an error."
    ))

    _virtualenv = None

    @observe("connection")
    def _on_connection_change(self, change):
        # Invalidate cached values
        self._virtualenv = None

    @property
    def is_local(self):
        try:
            return ipaddress.IPv4Address(self.connection["host"]).is_loopback
        except ipaddress.AddressValueError:
            return False

    @property
    def virtualenv(self):
        if self.is_local:
            return None
        if self._virtualenv is None:
            paths = self.exec_json("jupyter --paths --json")
            self._virtualenv = os.path.join(paths["data"][0], "hydra-kernel", "venv")
        return self._virtualenv

    def as_dict(self):
        return {
            trait: trait_type.get(self)
            for trait, trait_type in self.traits().items()
        }

    def _ssh_connect(self) -> "SSHClient":
        client = SSHClient()
        client.set_missing_host_key_policy(
            RejectPolicy if self.host_key_checking else AutoAddPolicy
        )
        try:
            client.connect(
                self.connection["host"],
                username=self.connection.get("user"),
                key_filename=self.connection.get("ssh_private_key_file"),
                timeout=self.connection.get("ssh_timeout", DEFAULT_SSH_TIMEOUT),
            )
        except NoValidConnectionsError as exc:
            raise BindingConnectionError(binding_name=self.name) from exc
        except SSHException as exc:
            raise BindingConnectionError(binding_name=self.name) from exc
        return client

    def exec(self, command: "typing.Union[list,str]", timeout=None) -> "tuple[int,io.RawIOBase,io.RawIOBase]":
        """Execute a command on the binding host.

        If the binding is a local binding, the command is executed directly, via
        `subprocess.run`. If a remote binding, the command is executed via
        a SSH session.

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
        if self.is_local:
            # In a kernel context, the STDOUT and STDERR file descriptors are
            # already piped to the iopub channel. Using `capture_output` will
            # pipe those fds again, which ends up deadlocking subprocess.run.
            # Instead, pipe both stdout and stderr to a temporary file.
            with tempfile.TemporaryFile() as tmpf:
                process = subprocess.run(
                    [shlex.quote(s) for s in command],
                    stdout=tmpf,
                    stderr=tmpf,
                    timeout=timeout,
                )
                # Reset stream for reading
                tmpf.seek(0)
                return process.returncode, io.BytesIO(tmpf.read()), io.BytesIO()
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

    def put_file(self, local_path: "str", remote_path: "str"):
        with self._ssh_connect() as ssh:
            scp = SCPClient(ssh.get_transport())
            scp.put(local_path, remote_path)


class BindingManager(object):

    _on_change_callback = None
    _binding_map = {}
    _kernel_map = {}

    def on_change(self, fn):
        if not callable(fn):
            raise ValueError("Callback argument must be callable")
        self._on_change_callback = fn

    def _on_change(self, change):
        binding = change.pop("owner", None)
        if not binding:
            return
        if self._on_change_callback:
            self._on_change_callback(binding, change)

    def set(self, name, kernel=None, connection=None):
        binding = self._binding_map.get(name)
        if not binding:
            binding = Binding()
            binding.set_trait("name", name)
            binding.observe(self._on_change)
            self._binding_map[name] = binding

        if kernel:
            binding.kernel = kernel
        if connection:
            binding.connection = connection

    def get(self, name) -> "Binding":
        return self._binding_map.get(name)

    def list(self) -> "list[Binding]":
        return self._binding_map.values()
