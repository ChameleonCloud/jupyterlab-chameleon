import logging
import os
import pathlib
import time
import typing
from signal import SIGKILL

from jupyter_client.channels import HBChannel
from jupyter_client.connect import port_names
from jupyter_client.ioloop.manager import IOLoopKernelManager
from jupyter_client.kernelspec import NoSuchKernel
from jupyter_client.multikernelmanager import DuplicateKernelError, MultiKernelManager
from jupyter_client.threaded import ThreadedKernelClient, ThreadedZMQSocketChannel
from jupyter_core.paths import jupyter_data_dir
from traitlets.traitlets import Type

from . import kernel_manager_factory

if typing.TYPE_CHECKING:
    from ..binding import Binding

LOG = logging.getLogger(__name__)
HYDRA_DATA_DIR = os.path.join(jupyter_data_dir(), "hydra-kernel")
pathlib.Path(HYDRA_DATA_DIR).mkdir(exist_ok=True)


# Do some subclassing to ensure we are spawning threaded clients
# for our proxy kernels (the default is blocking.)
class HydraChannel(ThreadedZMQSocketChannel):
    def __init__(self, socket, session, loop):
        super(HydraChannel, self).__init__(socket, session, loop)
        self._pipes = []

    def call_handlers(self, msg):
        for handler in self._pipes:
            handler(msg)

    def pipe(self, handler):
        self._pipes.append(handler)

    def unpipe(self):
        self._pipes = []


class HydraHBChannel(HBChannel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._handlers = []

    def call_handlers(self, since_last_heartbeat):
        super().call_handlers(since_last_heartbeat)
        for handler in self._handlers:
            try:
                handler(since_last_heartbeat)
            except RuntimeError:
                pass

    def add_handler(self, callback):
        self._handlers.append(callback)


class HydraKernelClient(ThreadedKernelClient):
    shell_channel_class = Type(HydraChannel)
    iopub_channel_class = Type(HydraChannel)
    hb_channel_class = Type(HydraHBChannel)


class HydraKernelManager(IOLoopKernelManager):
    client_class = "hydra_kernel.manager.base.HydraKernelClient"

    binding: "Binding" = None

    def __init__(self, *args, binding: "Binding" = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.binding = binding
        self.post_init(binding)

    def reset_ports(self):
        for name in port_names:
            setattr(self, name, 0)

    def post_init(self, binding: "Binding"):
        """A convenience function to perform post-init with a binding ref."""
        pass

    def pre_start_kernel(self, **kw):
        if hasattr(self.kernel_spec_manager, "provision_kernel_spec"):
            try:
                self.kernel_spec_manager.get_kernel_spec(self.kernel_name)
            except NoSuchKernel:
                LOG.info(
                    f"No kernel found for '{self.kernel_name}', attempting install"
                )
                self.kernel_spec_manager.provision_kernel_spec(
                    kernel_name=self.kernel_name
                )
        return super().pre_start_kernel(**kw)


class HydraMultiKernelManager(MultiKernelManager):
    connection_dir = HYDRA_DATA_DIR

    def pre_start_kernel(self, kernel_name, kwargs):
        # NOTE(jason): Must of this is lifted from the superclass implementation.
        # The main reason is that we need to pass an additional keyword argument
        # into the kernel manager factory; the superclass only allows a small
        # set of keyword arguments through.

        kernel_id = kwargs.pop("kernel_id", self.new_kernel_id(**kwargs))
        if kernel_id in self:
            raise DuplicateKernelError("Kernel already exists: %s" % kernel_id)

        if kernel_name is None:
            kernel_name = self.default_kernel_name

        binding = kwargs.pop("binding")

        km = self._create_kernel_manager(kernel_id, binding)
        # The kernelmanager knows its ID in case it needs to spawn subkernels;
        # tying to the parent ID makes it easier to trace ownership of subkernels.
        km.kernel_id = kernel_id

        return km, kernel_name, kernel_id

    def _create_kernel_manager(
        self, kernel_id: "str", binding: "Binding"
    ) -> "HydraKernelManager":
        # TODO: support different kernel managers based on binding connection type
        km_factory = kernel_manager_factory(binding)

        return km_factory(
            binding=binding,
            connection_file=os.path.join(
                self.connection_dir, "kernel-%s.json" % kernel_id
            ),
            parent=self,
            log=self.log,
            kernel_name=binding.kernel,
        )


class KernelProxy(object):
    def poll(self):
        try:
            if self.send_signal(0) != 0:
                return 0
        except ConnectionError:
            LOG.warning(f"Connection error when polling subkernel {self.binding}")
            # TODO: communicate this up to the client somehow?
        return None

    def wait(self, timeout=10):
        start = time.perf_counter()
        while True:
            if self.poll() is not None:
                return
            if time.perf_counter() - start > timeout:
                return
            time.sleep(1)

    def send_signal(self, signum):
        """Send a signal to the wrapped process.

        Subclasses should override this to define how the signal is sent.
        """
        raise NotImplementedError(
            "This connection type doesn't support process management"
        )

    def kill(self):
        return self.send_signal(SIGKILL)
