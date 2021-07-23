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

from hydra_kernel.utils import redirect_output
import io
import json
import logging
import os
import sys
import tempfile

import ansible_runner
from jupyter_client.kernelspec import KernelSpecManager, NoSuchKernel
from traitlets.traitlets import Instance

from hydra_kernel.binding import Binding, BindingState

LOG = logging.getLogger(__name__)


class RemoteKernelSpecManager(KernelSpecManager):
    """A kernel spec manager that provisions kernel specs on remote hosts.

    For supported kernels, an Ansible playbook is run against the remote host
    to install all dependencies for the kernel, and the kernel itself.

    To look up kernels, the manager connects via SSH to the host and inspects
    the default directories where kernelspecs are installed.
    """
    binding: "Binding" = Instance(Binding)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._kernelspecs = None
        self._kernelspec_info = {}
        if self.binding:
            self.binding.observe(self._on_connection_changed, "connection")

    def _invalidate_specs(self):
        self._kernelspecs = None
        self._kernelspec_info = {}

    def _on_connection_changed(self, change):
        self._invalidate_specs()

    def find_kernel_specs(self):
        if self.binding.is_local:
            return super().find_kernel_specs()

        if not self._kernelspecs:
            LOG.info(f"Fetching all kernel specs for '{self.binding.name}'")
            try:
                self._kernelspecs = self.binding.exec_json("jupyter kernelspec list --json")["kernelspecs"]
            except RuntimeError as exc:
                LOG.warn((
                    f"Failed to list kernel specs on {self.binding.name}: {exc}"
                ))

        kernelspecs = self._kernelspecs or {}

        return {
            name: spec["resource_dir"]
            for name, spec in kernelspecs.items()
        }

    def remove_kernel_spec(self, name):
        if self.binding.is_local:
            return super().remove_kernel_spec(name)
        else:
            raise NotImplementedError("Removing remote specs not yet supported")

    def get_kernel_spec(self, kernel_name):
        if self.binding.is_local:
            spec = super().get_kernel_spec(kernel_name)
        else:
            resource_dir = self.find_kernel_specs().get(kernel_name)
            if not resource_dir:
                raise NoSuchKernel(kernel_name)

            if resource_dir not in self._kernelspec_info:
                info_path = os.path.join(resource_dir, "kernel.json")
                with self.binding.get_file(info_path) as f:
                    self._kernelspec_info[resource_dir] = spec_info = json.load(f)
                    LOG.info((
                        f"Loaded {kernel_name} spec for {self.binding.name}: "
                        f"{spec_info}"))

            spec = self.kernel_spec_class(
                resource_dir=resource_dir,
                **self._kernelspec_info[resource_dir]
            )

        spec.argv = ["hydra-agent", f"--kernel={kernel_name}"]
        return spec

    def install_kernel_spec(self, source_dir, kernel_name, **kwargs):
        self._invalidate_specs()

        ansible_dir = os.path.join(sys.prefix, "share", "hydra-kernel", "ansible")
        host_vars = self._host_vars()

        with tempfile.TemporaryDirectory() as tmpdir:
            with redirect_output():
                runner = ansible_runner.run(
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
                    # Don't output to stdout, store as JSON instead
                    quiet=True,
                    json_mode=True,
                )
                LOG.info(runner.stdout.read())

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
        if self.binding.is_local:
            host_vars["ansible_connection"] = "local"
        return host_vars

    def _on_ansible_event(self, event):
        LOG.debug(f"ansible event: {event}")
