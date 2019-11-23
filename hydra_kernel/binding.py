from jupyter_client.multikernelmanager import MultiKernelManager
from jupyter_client.kernelspec import get_kernel_spec

from .kernelprovisioner import RemoteKernelProvisioner

class Binding(object):
  def __init__(self, name):
    self.name = name
    self.kernel = None

  @property
  def kernel_name(self):
    if (self.kernel):
      return self.kernel

class BindingManager(object):

  _bindings = {}

  def __init__(self):
    self.kernel_manager = MultiKernelManager()
    self.kernel_provisioner = RemoteKernelProvisioner()
    # TODO: load state from DB, if any

  def get_binding(self, binding_name):
    return self._bindings[binding_name]

  def start_kernel(self, binding_name):
    binding = self.get_binding(binding_name)
    get_kernel_spec(binding.kernel_name)
    # For this to work, 'kernel_name' must be a valid kernel that has already been installed
    # e.g. "bash" or "python". In our case, it will be something like "name_kernel" e.g. "node0_bash"
    self.kernel_manager.start_kernel(kernel_name=binding_name)

  def kernel_ready(self, binding_name):
    return self.kernel_manager.is_alive(self._kernel_map[binding_name])
