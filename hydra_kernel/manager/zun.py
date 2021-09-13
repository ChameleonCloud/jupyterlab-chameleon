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
import typing

from jupyter_client.connect import port_names

from .base import HydraKernelManager, KernelProxy

if typing.TYPE_CHECKING:
    from ..binding import Binding


class ZunHydraKernelManager(HydraKernelManager):
    def post_init(self, binding: "Binding"):
        self.ip = binding.connection.get("host")
        for port_name in port_names:
            setattr(self, port_name, binding.connection.get(port_name))

    def start_kernel(self, **kw):
        # SKIP actually starting the kernel, because we know it's already started!
        # We are just going to connect to it.
        self.kernel = ZunKernelProxy()
        self.post_start_kernel(**kw)


class ZunKernelProxy(KernelProxy):
    # Don't check so often that the kernel is down
    poll_interval = 30

    def send_signal(self, signum):
        if signum == 0:
            # Just check if container active
            # zun.container.get()
            return True
        else:
            # Send kill signal
            # zun.container.kill()
            return True
