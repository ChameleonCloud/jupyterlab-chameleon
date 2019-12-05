import logging
import sys
import time

from functools import partial

from ipykernel.jsonutil import json_clean
from ipykernel.ipkernel import IPythonKernel
from ipython_genutils import py3compat
from jupyter_client.ioloop.manager import IOLoopKernelManager
from jupyter_client.multikernelmanager import MultiKernelManager
from jupyter_client.threaded import ThreadedKernelClient, ThreadedZMQSocketChannel
from tornado import gen
from traitlets import Type

from .binding import BindingManager
from .magics import BindingMagics

__version__ = "0.0.1"

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
fh = logging.FileHandler("hydra.log")
fh.setLevel(logging.DEBUG)
LOG.addHandler(fh)

# Do some subclassing to ensure we are spawning threaded clients
# for our proxy kernels (the default is blocking.)
class MultiplexerZMQSocketChannel(ThreadedZMQSocketChannel):
    def __init__(self, socket, session, loop):
        super(MultiplexerZMQSocketChannel, self).__init__(socket, session, loop)
        self._pipes = []

    def call_handlers(self, msg):
        for handler in self._pipes:
            handler(msg)

    def pipe(self, handler):
        self._pipes.append(handler)

    def unpipe(self):
        self._pipes = []


class MultiplexerKernelClient(ThreadedKernelClient):
    shell_channel_class = Type(MultiplexerZMQSocketChannel)
    iopub_channel_class = Type(MultiplexerZMQSocketChannel)


class MultiplexerKernelManager(IOLoopKernelManager):
    client_class = "hydra_kernel.kernel.MultiplexerKernelClient"


class MultiplexerMultiKernelManager(MultiKernelManager):
    kernel_manager_class = "hydra_kernel.kernel.MultiplexerKernelManager"


class ProxyComms(object):
    def __init__(self, session, parent, iopub, shells):
        self.session = session
        self.parent = parent
        self.iopub = iopub
        self.shells = shells

        self._reply_content = None
        self._kernel_idle = False

    @property
    def reply_content(self):
        if not self._kernel_idle:
            return None
        return self._reply_content

    def on_iopub_message(self, msg):
        msg_type = msg["header"]["msg_type"]
        content = msg.get("content")
        LOG.info("IOPUB processing %s", msg_type)
        self.session.send(
            self.iopub,
            msg_type,
            content=content,
            parent=self.parent,
            metadata=msg.get("metadata"),
        )

        if msg_type == "status" and content["execution_state"] == "idle":
            LOG.info("IOPUB calling on idle return")
            self._kernel_idle = True

    def on_shell_message(self, msg):
        msg_type = msg["header"]["msg_type"]
        content = msg.get("content")
        LOG.info("SHELL processing %s", msg_type)
        if msg_type == "execute_request":
            # This message was sent ourselves and should not be
            # proxied back to the source.
            return

        for s in self.shells:
            self.session.send(
                s,
                msg_type,
                content=content,
                parent=self.parent,
                metadata=msg.get("metadata"),
            )

        if msg_type == "execute_reply":
            self._reply_content = content


class HydraKernel(IPythonKernel):
    """
    Hydra Kernel
    """

    implementation = "hydra_kernel"
    implementation_version = __version__

    language_info = {
        "name": "hydra",
        "codemirror_mode": "python",
        "mimetype": "text/python",
        "file_extension": ".py",
    }

    _kernels = {}

    def __init__(self, **kwargs):
        super(HydraKernel, self).__init__(**kwargs)
        self.binding_manager = BindingManager()
        # Register additional magics
        if self.shell:
            binding_magics = BindingMagics(self.shell, self.binding_manager)
            self.shell.register_magics(binding_magics)

        self.kernel_manager = MultiplexerMultiKernelManager()

    @property
    def banner(self):
        return "Hydra"

    @gen.coroutine
    def execute_request(self, stream, ident, parent):
        binding_name = parent["metadata"].get("chameleon.binding_name")

        if not binding_name:
            return super(HydraKernel, self).execute_request(stream, ident, parent)

        content = parent["content"]
        silent = content["silent"]
        stop_on_error = content.get("stop_on_error", True)

        # Check if binding name is valid (is there a binding set up?)
        if binding_name not in self._kernels:
            self.log.debug("Creating sub-kernel for %s", binding_name)
            kernel_id = self.kernel_manager.start_kernel('bash')
            km = self.kernel_manager.get_kernel(kernel_id)
            kc = km.client()
            # Only connect shell and iopub channels
            kc.start_channels(shell=True, iopub=True, stdin=False, hb=False)
            self._kernels[binding_name] = (km, kc)

        km, kc = self._kernels[binding_name]

        # TODO: add parent in here?
        msg = kc.session.msg("execute_request", content)
        self.log.debug("%s", msg)

        proxy = ProxyComms(self.session, parent, self.iopub_socket, self.shell_streams)

        kc.shell_channel.send(msg)
        kc.iopub_channel.pipe(proxy.on_iopub_message)
        kc.shell_channel.pipe(proxy.on_shell_message)

        while not proxy.reply_content:
            time.sleep(0.1)

        kc.iopub_channel.flush()
        kc.iopub_channel.unpipe()
        kc.shell_channel.unpipe()

        if not silent and reply_content["status"] == "error" and stop_on_error:
            yield self._abort_queues()

        # try:
        #     kc.shell_channel.send(msg)
        # except RuntimeError:
        #     LOG.exception("Killing kernel")
        #     self.log.exception("Failed to proxy message to sub kernel")
        #     kc.stop_channels()
        #     km.shutdown_kernel()
        #     raise
