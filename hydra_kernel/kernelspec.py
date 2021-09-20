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

from ipykernel import kernelspec
from jupyter_client.kernelspec import KernelSpec

if typing.TYPE_CHECKING:
    from .binding import Binding
    from .manager import HydraKernelManager


class HydraKernelSpecManager(kernelspec.KernelSpecManager):
    def get_kernel_spec(self, kernel_name):
        """Create proxy kernel specifications in-place of desired kernel."""
        parent: "HydraKernelManager" = self.parent
        binding: "Binding" = parent.binding
        provisioner_name = f"hydra_kernel:{binding.connection_type}"
        provisioner_config = {
            k: v for k, v in binding.connection.items() if k != "type"
        }
        provisioner_config["subkernel_name"] = binding.kernel

        return KernelSpec(
            argv=[],
            display_name=f"{kernel_name} ({binding.name})",
            language="",
            env={},
            resource_dir="",
            interrupt_mode="signal",
            metadata={
                "kernel_provisioner": {
                    "provisioner_name": provisioner_name,
                    "config": provisioner_config,
                },
            },
        )
