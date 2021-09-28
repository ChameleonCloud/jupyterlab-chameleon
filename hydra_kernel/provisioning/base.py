import asyncio
import io
import pathlib
import signal
import tarfile
import typing

from jupyter_client.provisioning import KernelProvisionerBase
from traitlets.traitlets import Float, Unicode

if typing.TYPE_CHECKING:
    from ..binding import Binding
    from ..manager import HydraKernelManager
    from typing import Optional


class HydraKernelProvisioner(KernelProvisionerBase):
    subkernel_name = Unicode()

    poll_interval = Float(1.0)

    @property
    def binding(self) -> "Binding":
        km: "HydraKernelManager" = self.parent
        assert hasattr(km, "binding")
        return km.binding

    async def kill(self, restart: bool = False) -> None:
        await self.send_signal(int(signal.SIGKILL))

    async def terminate(self, restart: bool = False) -> None:
        await self.send_signal(int(signal.SIGTERM))

    async def wait(self) -> "Optional[int]":
        ret = 0
        if self.has_process:
            while await self.poll() is None:
                await asyncio.sleep(self.poll_interval)

            self.reset()
        return ret

    async def cleanup(self, restart: bool = False) -> None:
        """No-op cleanup default implementation to satisfy base class."""
        pass

    def reset(self) -> None:
        """Reset the has_process state.

        In general, this function should modify the state of the provisioner
        such that has_process returns false.
        """
        pass


class FileManagementMixin:
    async def upload_path(self, local_path: "str", remote_path: "str" = None):
        raise NotImplementedError("Upload is not supported for this subkernel.")

    async def download_path(self, remote_path: "str", local_path: "str" = None):
        raise NotImplementedError("Download is not supported for this subkernel.")

    def prepare_upload(self, local_path: "str"):
        fd = io.BytesIO()
        path = pathlib.Path(local_path)
        arcname = "." if path.is_dir() else None

        with tarfile.open(fileobj=fd, mode="w:gz") as tar:
            tar.add(local_path, arcname=arcname)
        fd.seek(0)

        return fd
