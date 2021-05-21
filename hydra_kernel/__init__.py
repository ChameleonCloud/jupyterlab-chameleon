import logging

from .kernel import HydraKernel, __version__

logging.basicConfig(handlers=[logging.FileHandler("hydra.log")], level=logging.DEBUG)


__all__ = ["__version__", "HydraKernel"]
