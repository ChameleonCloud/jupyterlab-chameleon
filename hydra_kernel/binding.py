import logging

from traitlets.traitlets import Dict, Enum, HasTraits, Unicode, default

from hydra_kernel.exception import HydraException

LOG = logging.getLogger(__name__)

DEFAULT_KERNEL = "python"
SUPPORTED_KERNELS = ("bash", "python")
MIME_TYPES = {
    "bash": "shell",
    "python": "python",
}


# TODO: figure out how to properly integrate this into enum.Enum and
# traitlet.Enum.
class BindingState:
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RESTARTED = "restarted"
    CREATING = "creating"
    ERROR = "error"


class BindingConnectionType:
    LOCAL = "local"
    SSH = "ssh"
    ZUN = "zun"


class BindingConnectionError(HydraException):
    _msg_fmt = "Could not connect to binding %(binding_name)s"


class Binding(HasTraits):
    name = Unicode(read_only=True)
    kernel = Enum(SUPPORTED_KERNELS, default_value=DEFAULT_KERNEL)
    mime_type = Unicode()
    connection = Dict()
    state = Enum(
        [
            BindingState.CONNECTED,
            BindingState.DISCONNECTED,
            BindingState.RESTARTED,
            BindingState.CREATING,
            BindingState.ERROR,
        ],
        default_value=BindingState.DISCONNECTED,
    )
    progress = Dict(default_value={"progress": None, "progress_ratio": None})

    def __str__(self):
        conn_info = [
            f"  {key}={value}"
            for key, value in self.connection.items()
            if value is not None
        ]
        return "\n".join(
            [
                self.name,
                f" {self.state}",
                f" Connection: {self.connection_type}",
                "\n".join(conn_info),
            ]
        )

    @default("mime_type")
    def _default_mime_type(self):
        return MIME_TYPES.get(self.kernel, "unknown")

    @property
    def connection_type(self):
        return self.connection.get("type", BindingConnectionType.SSH)

    def update_progress(self, message: "str", ratio: "float" = None):
        self.progress = {"progress": message, "progress_ratio": ratio}

    def as_dict(self):
        return {
            trait: trait_type.get(self) for trait, trait_type in self.traits().items()
        }


class BindingManager(object):

    _on_change_callback = None
    _on_remove_callback = None
    _binding_map = {}
    _kernel_map = {}

    def on_change(self, fn):
        if not callable(fn):
            raise ValueError("Callback argument must be callable")
        self._on_change_callback = fn

    def on_remove(self, fn):
        if not callable(fn):
            raise ValueError("Callback argument must be callable")
        self._on_remove_callback = fn

    def _on_change(self, change):
        binding = change.pop("owner", None)
        if not binding:
            return
        if self._on_change_callback:
            self._on_change_callback(binding, change)

    def set(
        self,
        name,
        kernel: "str" = None,
        connection: "dict" = None,
        state: "str" = None,
    ):
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
        if state:
            binding.state = state

    def get(self, name) -> "Binding":
        return self._binding_map.get(name)

    def list(self) -> "list[Binding]":
        return self._binding_map.values()

    def delete(self, name):
        if name not in self._binding_map:
            raise ValueError("Binding not found")
        binding = self._binding_map[name]
        del self._binding_map[name]
        if self._on_remove_callback:
            self._on_remove_callback(binding)
