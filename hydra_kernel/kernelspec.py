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
import sys

import ansible_runner
from jupyter_client.kernelspec import KernelSpecManager
from traitlets.traitlets import Instance

from hydra_kernel.binding import Binding

LOG = logging.getLogger(__name__)


class RemoteKernelSpecManager(KernelSpecManager):
    """A kernel spec manager that provisions kernel specs on remote hosts.

    For supported kernels, an Ansible playbook is run against the remote host
    to install all dependencies for the kernel, and the kernel itself.

    To look up kernels, the manager connects via SSH to the host and inspects
    the default directories where kernelspecs are installed.
    """
    binding = Instance(Binding)

    def find_kernel_specs(self):
        LOG.debug("find_kernel_specs")
        self.binding.exec("ls -al /etc")
        return super().find_kernel_specs()

    def remove_kernel_spec(self, name):
        return super().remove_kernel_spec(name)

    def get_kernel_spec(self, kernel_name):
        LOG.debug(f"get_kernel_spec: {kernel_name}")
        with self.binding.get_file("/etc/resolv.conf") as f:
            LOG.debug(f.read().decode("utf-8"))
        # TODO: this really needs to look up the paths on the host directly.
        # For now, we assume kernels are installed in /etc/jupyter or
        # /usr/local/share/jupyter
        # dirs = jupyter_path("kernels")
        return super().get_kernel_spec(kernel_name)

    def install_kernel_spec(self, _, kernel_name, **kwargs):
        LOG.debug(f"install_kernel_spec: {kernel_name}")
        data_dir = os.path.join(sys.prefix, "share", "hydra-kernel")
        host_vars = self._host_vars()

        ansible_runner.run(
            private_data_dir=data_dir,
            project_dir="ansible",
            inventory={
                "all": {
                    "hosts": {
                        "KERNEL": host_vars
                    }
                }
            },
            playbook="kernel_action.yml",
            extravars={
                "kernel_name": kernel_name,
                "kernel_action": "start"
            },
            event_handler=self._on_ansible_event,
        )

    def _host_vars(self):
        conn = self.binding.connection
        host = conn["host"]
        host_vars = {
            "ansible_host": host,
            "ansible_user": conn.get("user"),
            "ansible_become": conn.get("sudo", False),
            "ansible_ssh_private_key_file": conn.get("ssh_private_key_file"),
            # TODO: handle "via"
        }
        if self.binding.is_loopback:
            host_vars["ansible_connection"] = "local"
        return host_vars

    def _on_ansible_event(self, event):
        LOG.debug(f"ansible event: {event}")
