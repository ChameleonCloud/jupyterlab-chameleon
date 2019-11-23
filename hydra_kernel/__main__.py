from ipykernel.kernelapp import IPKernelApp

from .kernel import HydraKernel

IPKernelApp.launch_instance(kernel_class=HydraKernel)
