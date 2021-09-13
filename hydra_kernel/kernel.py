import logging
import time
from functools import partial
import typing

from ipykernel.comm import Comm
from ipykernel.ipkernel import IPythonKernel
from jupyter_client.connect import port_names
from tornado import gen

from .binding import (
    Binding,
    BindingManager,
    BindingState,
)
from .manager.base import HydraMultiKernelManager
from .magics import BindingMagics

if typing.TYPE_CHECKING:
    from .manager.base import HydraKernelManager, HydraKernelClient, HydraHBChannel

LOG = logging.getLogger(__name__)
KERNEL_HEARTBEAT_TIMEOUT = 60  # seconds

__version__ = "0.0.1"


class ProxyComms(object):
    def __init__(self, session, ident=None, parent=None, iopub=None, shell=None):
        self.session = session
        self.parent = parent
        self.iopub = iopub
        self.shell = shell
        self.ident = ident

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
        LOG.debug("IOPUB processing %s", msg_type)
        self.session.send(
            self.iopub,
            msg_type,
            content=content,
            parent=self.parent,
            metadata=msg.get("metadata"),
        )

        if msg_type == "status" and content["execution_state"] == "idle":
            LOG.debug("IOPUB calling on idle return")
            self._kernel_idle = True

    def on_shell_message(self, msg):
        msg_type = msg["header"]["msg_type"]
        content = msg.get("content")
        LOG.debug("SHELL processing %s", msg_type)
        if msg_type == "execute_request":
            # This message was sent ourselves and should not be
            # proxied back to the source.
            return

        self.session.send(
            self.shell,
            msg_type,
            ident=self.ident,
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

    log = LOG

    implementation = "hydra_kernel"
    implementation_version = __version__

    language_info = {
        "name": "hydra",
        "codemirror_mode": "python",
        "mimetype": "text/python",
        "file_extension": ".py",
    }

    _subkernels: "dict[str,HydraKernelManager]" = {}
    _clients: "dict[HydraKernelManager,HydraKernelClient]" = {}
    _comm: "Comm" = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.binding_manager = BindingManager()
        if self.shell:
            binding_magics = BindingMagics(self.shell, self.binding_manager)
            self.shell.register_magics(binding_magics)

        self.binding_manager.on_change(self.on_binding_change)
        self.binding_manager.on_remove(self.on_binding_remove)
        self.kernel_manager = HydraMultiKernelManager()

    def start(self):
        super().start()
        LOG.debug("Registering comm channel")
        self.comm_manager.register_target("hydra", self.on_comm_open)

    def do_shutdown(self, restart):
        # Also shut down all managed subkernels
        for kernel_id in self.kernel_manager.list_kernel_ids():
            LOG.info(f"Shutting down subkernel {kernel_id}")
            kernel: "HydraKernelManager" = self.kernel_manager.get_kernel(kernel_id)
            kernel.shutdown_kernel(restart=restart)

        return super().do_shutdown(restart)

    def on_comm_open(self, comm: "Comm", message: "dict"):
        if self._comm:
            self._comm.on_msg(None)
        self._comm = comm
        self._comm.on_msg(self.on_comm_msg)
        LOG.debug(f"Registered comm channel {comm} with open request {message}")

    def on_binding_change(self, binding: "Binding", change: "dict"):
        if self._comm:
            self._comm.send({"event": "binding_update", "binding": binding.as_dict()})

    def on_binding_remove(self, binding: "Binding"):
        try:
            kernel_id = self._subkernels[binding.name].kernel_id
            self.kernel_manager.shutdown_kernel(kernel_id)
            del self._subkernels[binding.name]
        except Exception as exc:
            self.log.error(f"Failed to tear down kernel for {binding.name}: {exc}")

        if self._comm:
            self._comm.send(
                {
                    "event": "binding_remove",
                    "binding": binding.as_dict(),
                }
            )

    def on_comm_msg(self, message: "dict"):
        payload = message.get("content", {}).get("data", {})
        LOG.info(f"Got message: {payload}")
        if payload["event"] == "binding_list_request":
            if self._comm:
                self._comm.send(
                    {
                        "event": "binding_list_reply",
                        "bindings": [b.as_dict() for b in self.binding_manager.list()],
                    }
                )

    @property
    def banner(self):
        return "Hydra"

    @gen.coroutine
    def execute_request(self, stream, ident, parent):
        binding_name = parent["metadata"].get("chameleon.binding_name")

        if not binding_name:
            return super(HydraKernel, self).execute_request(stream, ident, parent)

        binding = self.binding_manager.get(binding_name)

        if not binding:
            raise ValueError(f"No such binding {binding_name} exists")

        content = parent["content"]
        silent = content["silent"]
        stop_on_error = content.get("stop_on_error", True)

        # Check if binding name is valid (is there a binding set up?)
        if binding_name not in self._subkernels:
            binding.state = BindingState.CREATING
            self.log.info(f"{binding_name}: starting subkernel")
            try:
                kernel_id: "str" = self.kernel_manager.start_kernel(
                    binding.kernel, binding=binding
                )
            except Exception as exc:
                self.log.exception(f"Failed to start subkernel for '{binding_name}'")
                self.binding_manager.set(binding_name, state=BindingState.DISCONNECTED)
                return

            km: "HydraKernelManager" = self.kernel_manager.get_kernel(kernel_id)
            km.add_restart_callback(partial(self.on_subkernel_restart, binding_name))
            km.observe(self.on_subkernel_ports_changed, names=port_names)
            self._subkernels[binding_name] = km

        km = self._subkernels[binding_name]

        # TODO: it is possible to restart the kernel, which will kill the SSH
        # tunnels. We need to recreate them as part of start_channels.

        if km not in self._clients:
            self.log.info(f"{binding_name}: connecting to sub-kernel")
            kc: "HydraKernelClient" = km.client()
            # Currently piping to stdin channel is not supported
            kc.start_channels(stdin=False)
            hb_channel: "HydraHBChannel" = kc.hb_channel
            hb_channel.add_handler(partial(self.on_subkernel_disconnect, binding_name))
            self._clients[km] = kc

        self.on_subkernel_connect(binding_name)

        kc = self._clients[km]
        proxy = ProxyComms(
            self.session,
            ident=ident,
            parent=parent,
            iopub=self.iopub_socket,
            shell=stream,
        )
        kc.iopub_channel.pipe(proxy.on_iopub_message)
        kc.shell_channel.pipe(proxy.on_shell_message)
        msg = kc.session.msg("execute_request", content)
        kc.shell_channel.send(msg)

        # This will effectively block, but perhaps that is a good thing.
        # Without blocking, it seems to allow multiple cells to execute in parallel.
        while not proxy.reply_content:
            time.sleep(0.1)

        # Ensure there's nothing that still needs to be proxied and cleanup.
        kc.shell_channel.flush()
        kc.shell_channel.unpipe()
        kc.iopub_channel.flush()
        kc.iopub_channel.unpipe()

        if not silent and proxy.reply_content["status"] == "error" and stop_on_error:
            yield self._abort_queues()

    def on_subkernel_ports_changed(self, change):
        km: "HydraKernelManager" = change["owner"]
        kc = self._clients.pop(km, None)
        if kc:
            kc.stop_channels()

    def on_subkernel_restart(self, binding_name):
        self.log.info(f"{binding_name}: subkernel restarted")
        self.binding_manager.set(binding_name, state=BindingState.RESTARTED)

    def on_subkernel_connect(self, binding_name):
        self.log.info(f"{binding_name}: subkernel connected")
        self.binding_manager.set(binding_name, state=BindingState.CONNECTED)

    def on_subkernel_disconnect(self, binding_name, since_last_heartbeat):
        # The subkernels take a bit to initialize, during which time the
        # heartbeat failure can trigger a few times. Wait until some timeout
        # to actually trip the state to disconnected.
        if since_last_heartbeat > KERNEL_HEARTBEAT_TIMEOUT:
            self.log.info(f"{binding_name}: subkernel disconnected")
            self.binding_manager.set(binding_name, state=BindingState.DISCONNECTED)
