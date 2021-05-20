import ipaddress

from traitlets.traitlets import Enum, HasTraits, Dict, Unicode

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
