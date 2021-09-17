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

from ..binding import BindingConnectionType

if typing.TYPE_CHECKING:
    from ..binding import Binding


def kernel_manager_factory(binding: "Binding"):
    if binding.connection_type == BindingConnectionType.SSH:
        from .ssh import SSHHydraKernelManager

        return SSHHydraKernelManager
    elif binding.connection_type == BindingConnectionType.LOCAL:
        from .local import LocalHydraKernelManager

        return LocalHydraKernelManager
    elif binding.connection_type == BindingConnectionType.ZUN:
        from .zun import ZunHydraKernelManager

        return ZunHydraKernelManager
    else:
        raise ValueError("Unsupported connection type")
