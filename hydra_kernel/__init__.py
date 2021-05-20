import logging

from .kernel import HydraKernel, __version__

logging.basicConfig()
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
LOG.addHandler(logging.FileHandler("hydra.log"))

__all__ = ["__version__", "HydraKernel"]
