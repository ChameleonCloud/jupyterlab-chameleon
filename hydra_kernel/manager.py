# Copyright 2021 University of Chicago
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
import os
import pathlib
import typing

from jupyter_client.channels import HBChannel
from jupyter_client.ioloop.manager import IOLoopKernelManager
from jupyter_client.multikernelmanager import DuplicateKernelError, MultiKernelManager
from jupyter_client.threaded import ThreadedKernelClient, ThreadedZMQSocketChannel
from jupyter_core.paths import jupyter_data_dir
from traitlets.traitlets import Instance, Type, default

from .binding import Binding
from .kernelspec import HydraKernelSpecManager

if typing.TYPE_CHECKING:
    from typing import Callable

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
    client_class = "hydra_kernel.manager.HydraKernelClient"

    @default("kernel_spec_manager")
    def _default_kernel_spec_manager(self):
        return HydraKernelSpecManager(parent=self)

    binding = Instance(Binding)

    # TODO: refresh kernel spec manager (??) if the binding connection changes.
    # Not sure if that is really necessary.

    @property
    def kernel_name(self):
        """Override kernel name to refer to subkernel"""
        return self.binding.kernel


class HydraMultiKernelManager(MultiKernelManager):
    connection_dir = HYDRA_DATA_DIR

    def pre_start_kernel(self, kernel_name, kwargs):
        # NOTE(jason): Must of this is lifted from the superclass implementation.
        # The main reason is that we need to pass an additional keyword argument
        # into the kernel manager ctor; the superclass only allows a small
        # set of keyword arguments through.
        kernel_id = kwargs.pop("kernel_id", self.new_kernel_id(**kwargs))
        if kernel_id in self:
            raise DuplicateKernelError("Kernel already exists: %s" % kernel_id)

        binding: "Binding" = kwargs.pop("binding")
        km = HydraKernelManager(
            binding=binding,
            connection_file=os.path.join(
                self.connection_dir, "kernel-%s.json" % kernel_id
            ),
            parent=self,
            log=self.log,
        )
        # The kernelmanager knows its ID in case it needs to spawn subkernels;
        # tying to the parent ID makes it easier to trace ownership of subkernels.
        km.kernel_id = kernel_id

        return km, binding.kernel, kernel_id
