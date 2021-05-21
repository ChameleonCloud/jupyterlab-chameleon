from contextlib import contextmanager
import io
import ipaddress
import logging
import tempfile
import typing

from paramiko.client import AutoAddPolicy, SSHClient
from paramiko.ssh_exception import SSHException
from scp import SCPClient
from traitlets.traitlets import Enum, HasTraits, Dict, Unicode

if typing.TYPE_CHECKING:
    from paramiko.channel import ChannelFile, ChannelStderrFile

LOG = logging.getLogger(__name__)

DEFAULT_KERNEL = 'bash'
SUPPORTED_KERNELS = (
    'bash', 'python'
)

class Binding(HasTraits):
    name = Unicode(read_only=True)
    kernel = Enum(SUPPORTED_KERNELS, default_value=DEFAULT_KERNEL)
    connection = Dict()

    @property
    def is_loopback(self):
        try:
            return ipaddress.IPv4Address(self.connection["host"]).is_loopback
        except ipaddress.AddressValueError:
            return False

    def as_dict(self):
        return {
            trait: trait_type.get(self)
            for trait, trait_type in self.traits().items()
        }

    def _ssh_connect(self) -> "SSHClient":
        client = SSHClient()
        # TODO: allow configuring host key checking
        client.set_missing_host_key_policy(AutoAddPolicy)
        client.connect(
            self.connection["host"],
            username=self.connection.get("user"),
            key_filename=self.connection.get("ssh_private_key_file"),
        )
        return client

    def exec(self, command: "str", timeout=None) -> "tuple[int,ChannelFile,ChannelStderrFile]":
        with self._ssh_connect() as ssh:
            _, stdout, stderr = ssh.exec_command(command, timeout=timeout)
            return stdout.channel.recv_exit_status(), stdout, stderr

    @contextmanager
    def get_file(self, path: "str") -> "io.BytesIO":
        with self._ssh_connect() as ssh:
            scp = SCPClient(ssh.get_transport())
            with tempfile.NamedTemporaryFile() as tmpf:
                LOG.debug(f"{path} -> {tmpf.name}")
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
