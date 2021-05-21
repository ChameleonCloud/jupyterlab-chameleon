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

import json
import logging
import os
import sys
import tempfile

import ansible_runner
from jupyter_client.kernelspec import KernelSpecManager, NoSuchKernel
import paramiko
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
    binding: "Binding" = Instance(Binding)

    def find_kernel_specs(self):
        if self.binding.is_loopback:
            return super().find_kernel_specs()

        LOG.debug("find_kernel_specs")

        kernelspecs = {}
        try:
            code, stdout, stderr = self.binding.exec(
                "python -m jupyter_core kernelspec list --json"
            )
            if code == 0:
                kernelspecs = json.loads(stdout.read())["kernelspecs"]
            else:
                LOG.warn((
                    f"Failed to list kernel specs on {self.binding.name}: "
                    f"{stderr.read()}"
                ))
        except json.JSONDecodeError:
            pass

        return {
            name: spec["resource_dir"]
            for name, spec in kernelspecs.items()
        }

    def remove_kernel_spec(self, name):
        if self.binding.is_loopback:
            return super().remove_kernel_spec(name)

    def get_kernel_spec(self, kernel_name):
        if self.binding.is_loopback:
            return super().get_kernel_spec(kernel_name)

        resource_dir = self.find_kernel_specs().get(kernel_name)
        if not resource_dir:
            raise NoSuchKernel(kernel_name)

        with self.binding.get_file(os.path.join(resource_dir, "kernel.json")) as f:
            return self.kernel_spec_class(
                resource_dir=resource_dir,
                **json.load(f)
            )

    def install_kernel_spec(self, source_dir, kernel_name, **kwargs):
        if self.binding.is_loopback:
            return super().install_kernel_spec(source_dir, kernel_name=kernel_name, **kwargs)

        LOG.debug(f"install_kernel_spec: {kernel_name}")
        ansible_dir = os.path.join(sys.prefix, "share", "hydra-kernel", "ansible")
        host_vars = self._host_vars()

        with tempfile.TemporaryDirectory() as tmpdir:
            ansible_runner.run(
                private_data_dir=tmpdir,
                project_dir=ansible_dir,
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
                    "kernel_action": "install",
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
