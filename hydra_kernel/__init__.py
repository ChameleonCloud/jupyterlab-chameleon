import logging

from .kernel import HydraKernel, __version__

DEBUG = True
if DEBUG:
    log_level = logging.DEBUG
    paramiko_level = logging.DEBUG
else:
    log_level = logging.INFO
    # Paramiko is very chatty
    paramiko_level = logging.WARN

logging.basicConfig(handlers=[logging.FileHandler("hydra.log")], level=log_level)
logging.getLogger("paramiko").setLevel(paramiko_level)

__all__ = ["__version__", "HydraKernel"]
