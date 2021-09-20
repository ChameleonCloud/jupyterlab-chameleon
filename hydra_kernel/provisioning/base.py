import asyncio
import signal
import typing

from jupyter_client.provisioning import KernelProvisionerBase
from traitlets.traitlets import Float, Unicode

if typing.TYPE_CHECKING:
    from ..manager import HydraKernelManager
    from typing import Optional


class HydraKernelProvisioner(KernelProvisionerBase):
    subkernel_name = Unicode()

    poll_interval = Float(1.0)

    @property
    def binding(self):
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
