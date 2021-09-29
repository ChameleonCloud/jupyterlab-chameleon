import logging
import os

from .kernel import HydraKernel, __version__

DEBUG = os.environ.get("HYDRA_KERNEL_DEBUG", "0") == "1"

if DEBUG:
    log_level = logging.DEBUG
    paramiko_level = logging.DEBUG
else:
    log_level = logging.INFO
    # Paramiko is very chatty
    paramiko_level = logging.WARN

logging.basicConfig(level=log_level)
logging.getLogger("paramiko").setLevel(paramiko_level)

__all__ = ["__version__", "HydraKernel"]
