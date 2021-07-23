from functools import partial
import logging
import os
import pathlib
import shlex
from signal import SIGKILL
import subprocess
import time
import typing

from ipykernel.comm import Comm
from ipykernel.ipkernel import IPythonKernel
from jupyter_client.channels import HBChannel
from jupyter_client.connect import port_names, tunnel_to_kernel
from jupyter_client.ioloop.manager import IOLoopKernelManager
from jupyter_client.kernelspec import NoSuchKernel
from jupyter_client.multikernelmanager import MultiKernelManager
from jupyter_client.threaded import ThreadedKernelClient, ThreadedZMQSocketChannel
from jupyter_core.paths import jupyter_data_dir
from tornado import gen
from traitlets.traitlets import Bool, Type

from .binding import Binding, BindingConnectionError, BindingManager, BindingState
from .kernelspec import RemoteKernelSpecManager
from .magics import BindingMagics
from .utils import redirect_output

if typing.TYPE_CHECKING:
    from jupyter_client import KernelClient, KernelManager

LOG = logging.getLogger(__name__)
HYDRA_DATA_DIR = os.path.join(jupyter_data_dir(), "hydra-kernel")

pathlib.Path(HYDRA_DATA_DIR).mkdir(exist_ok=True)

__version__ = "0.0.1"


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
    client_class = "hydra_kernel.kernel.HydraKernelClient"

    # Tell the multi-kernel manager NOT to cache the auto-assigned ports;
    # the kernel manager will override them after launching the subkernel.
    cache_ports = False

    tunnel = Bool(True, help=(
        "If set, connection to remote kernel will be established over an SSH "
        "tunnel. Remote kernels on loopback hosts will not have tunnels."
    ))

    binding: Binding = None

    @property
    def needs_tunnel(self):
        return self.tunnel and not self.binding.is_local

    def init_binding(self, kernel_id, binding: Binding):
        self.binding = binding
        self.kernel_id = kernel_id
        self.kernel_spec_manager = RemoteKernelSpecManager(binding=binding)

    def pre_start_kernel(self, **kw):
        try:
            self.kernel_spec_manager.get_kernel_spec(self.kernel_name)
        except NoSuchKernel:
            LOG.info(f"No kernel found for '{self.kernel_name}', attempting install")
            self.kernel_spec_manager.install_kernel_spec(None, kernel_name=self.kernel_name)
        return super().pre_start_kernel(**kw)

    def format_kernel_cmd(self, extra_arguments):
        cmd = super().format_kernel_cmd(extra_arguments=extra_arguments)
        cmd.append(f"--id={self.kernel_id}")
        if self.binding.virtualenv:
            venv_bin = os.path.join(self.binding.virtualenv, "bin")
            cmd[0] = os.path.join(venv_bin, cmd[0])
            cmd.append(f"--launcher={os.path.join(venv_bin, 'hydra-subkernel')}")

        return cmd

    def _reset_ports(self):
        for name in port_names:
            setattr(self, name, 0)

    def _save_host_key(self, host):
        hosts_file_path = pathlib.Path(
            pathlib.Path.home(), ".ssh", "known_hosts")
        hosts_file_path.parent.mkdir(exist_ok=True)
        hosts_file_path.touch()
        with hosts_file_path.open("a") as hosts_file:
            with redirect_output() as stderr:
                proc = subprocess.run(
                    shlex.split(f"ssh-keyscan -H {host}"),
                    stdout=hosts_file,
                    stderr=stderr
                )
                if proc.returncode != 0:
                    LOG.warning((
                        f"Failed to update host key for {host}: "
                        f"{proc.stderr.read()}"
                    ))

    def _launch_kernel(self, kernel_cmd, **kw):
        # The connection file has already been written as part of `pre_start_kernel`,
        # but we are going to be overriding ports to the subkernel's exposed
        # ports (or ports exposed via a SSH tunnel).
        self._reset_ports()
        self.cleanup_connection_file()

        LOG.info(f"{self.binding.name}: kernel_cmd={kernel_cmd}")
        subkernel = self.binding.exec_json(kernel_cmd)

        conn_info = subkernel["connection"]
        self.load_connection_info(conn_info)
        LOG.info(f"{self.binding.name}: connection={conn_info}")

        if self.needs_tunnel:
            conn = self.binding.connection
            sshkey = conn.get("ssh_private_key_file")
            sshserver = f"{conn.get('user')}@{conn['host']}"

            if not self.binding.host_key_checking:
                self._save_host_key(conn["host"])

            LOG.info(f"{self.binding.name}: tunneling to {sshserver}")

            (
                self.shell_port,
                self.iopub_port,
                self.stdin_port,
                self.hb_port,
                self.control_port
            ) = tunnel_to_kernel(conn_info, sshserver, sshkey=sshkey)

        self.write_connection_file()

        return ProcessProxy(self.binding, subkernel["pid"])


class ProcessProxy(object):
    def __init__(self, binding, pid):
        self.binding = binding
        self.pid = pid

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
        try:
            code, _, _ = self.binding.exec(f"kill -{signum} {self.pid}")
        except BindingConnectionError as exc:
            LOG.error(f"{self.binding.name}: failed to send signal due to {exc}")
            code = -1
        return code

    def kill(self):
        return self.send_signal(SIGKILL)


class HydraMultiKernelManager(MultiKernelManager):
    kernel_manager_class = "hydra_kernel.kernel.HydraKernelManager"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connection_dir = HYDRA_DATA_DIR

    def pre_start_kernel(self, kernel_name, kwargs):
        ret: "tuple[HydraKernelManager,str,str]" = super().pre_start_kernel(kernel_name, kwargs)
        (km, kernel_name, kernel_id) = ret
        km.init_binding(kernel_id, kwargs.pop("binding"))
        return km, kernel_name, kernel_id


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
            self._comm.send({
                "event": "binding_update",
                "binding": binding.as_dict()
            })

    def on_comm_msg(self, message: "dict"):
        payload = message.get("content", {}).get("data", {})
        LOG.info(f"Got message: {payload}")
        if payload["event"] == "binding_list_request":
            if self._comm:
                self._comm.send({
                    "event": "binding_list_reply",
                    "bindings": [
                        b.as_dict() for b in self.binding_manager.list()
                    ]
                })

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
            self.log.info(f"{binding_name}: starting sub-kernel")
            kernel_id: "str" = self.kernel_manager.start_kernel(binding.kernel, binding=binding)
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
            self.on_subkernel_connect(binding_name)
            self._clients[km] = kc

        kc = self._clients[km]
        proxy = ProxyComms(self.session, ident=ident, parent=parent, iopub=self.iopub_socket, shell=stream)
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
        self.binding_manager.set(binding_name, state=BindingState.RESTARTED)

    def on_subkernel_connect(self, binding_name):
        self.binding_manager.set(binding_name, state=BindingState.CONNECTED)

    def on_subkernel_disconnect(self, binding_name, since_last_heartbeat):
        self.binding_manager.set(binding_name, state=BindingState.DISCONNECTED)
