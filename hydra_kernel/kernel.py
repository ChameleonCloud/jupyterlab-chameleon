import sys
import time

from ipykernel.jsonutil import json_clean
from ipykernel.ipkernel import IPythonKernel
from ipython_genutils import py3compat
from tornado import gen

from .binding import BindingManager
from .magics import BindingMagics

__version__ = '0.0.1'

class HydraKernel(IPythonKernel):
    """
    Hydra Kernel
    """
    implementation = 'hydra_kernel'
    implementation_version = __version__

    language_info = {'name': 'hydra',
                     'codemirror_mode': 'python',
                     'mimetype': 'text/python',
                     'file_extension': '.py'}

    def __init__(self, **kwargs):
        super(HydraKernel, self).__init__(**kwargs)
        self.binding_manager = BindingManager()
        # Register additional magics
        if self.shell:
            binding_magics = BindingMagics(self.shell, self.binding_manager)
            self.shell.register_magics(binding_magics)


    @property
    def banner(self):
        return 'Hydra'


    @gen.coroutine    
    def execute_request(self, stream, ident, parent):
        binding_name = parent['metadata'].get('chameleon.binding_name')

        if not binding_name:
            return super(HydraKernel, self).execute_request(stream, ident, parent)

        # 1. Initial checks for sanity of binding/kernel

        # Check if binding name is valid

        # Check if kernel is running/exists. If not, start/create it.
        if not self.binding_manager.kernel_ready(binding_name):
            pass

        # 2. Proxying of message to subkernel
        
        # Re-route iopub from proxy kernel to this stdout/stderr so we can catch it.

        # Re-route stdin?

        # Re-send the request, wrap the message using parent headers (?)

        # Unroute stdin
        pass
