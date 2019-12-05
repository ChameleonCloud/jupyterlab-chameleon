import json
import os

from jupyter_client.multikernelmanager import MultiKernelManager
from jupyter_client.kernelspec import get_kernel_spec, install_kernel_spec, NoSuchKernel
from remote_ikernel.manage import add_kernel
from tempfile import TemporaryDirectory

DEFAULT_KERNEL = 'bash'
SUPPORTED_KERNELS = (
    'bash', 'python'
)

class Binding(object):

    kernel = None

    def __init__(self, name, kernel=None, connection=None):
        self.name = name

        if kernel:
            if not (kernel in SUPPORTED_KERNELS):
                raise ValueError(f'Kernel {kernel} is not a supported value!')
            self.kernel = kernel
        else:
            self.kernel = DEFAULT_KERNEL
    


class BindingManager(object):

    _binding_map = {}
    _kernel_map = {}
