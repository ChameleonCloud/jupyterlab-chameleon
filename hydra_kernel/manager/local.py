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
import io
import json
import logging
import os
import shlex
import subprocess
import tempfile

from .base import HydraKernelManager, KernelProxy

LOG = logging.getLogger(__name__)


class LocalHydraKernelManager(HydraKernelManager):
    @property
    def kernel_cmd(self):
        return [
            "hydra-agent",
            f"--kernel={self.binding.kernel}",
            f"--id={self.kernel_id}",
        ]

    def _launch_kernel(self, kernel_cmd, **kw):
        # The connection file has already been written as part of `pre_start_kernel`,
        # but we are going to be overriding ports to the subkernel's exposed
        # ports (or ports exposed via a SSH tunnel).
        self.reset_ports()
        self.cleanup_connection_file()

        LOG.info(f"{self.binding.name}: kernel_cmd={kernel_cmd}")
        if isinstance(kernel_cmd, str):
            command = shlex.split(kernel_cmd)
        else:
            command = [shlex.quote(arg) for arg in kernel_cmd]
        # In a kernel context, the STDOUT and STDERR file descriptors are
        # already piped to the iopub channel. Using `capture_output` will
        # pipe those fds again, which ends up deadlocking subprocess.run.
        # Instead, pipe both stdout and stderr to a temporary file.
        with tempfile.TemporaryFile() as tmpf:
            process = subprocess.run(
                command,
                stdout=tmpf,
                stderr=tmpf,
            )
            # Reset stream for reading
            tmpf.seek(0)
            stdout = io.BytesIO(tmpf.read())
            LOG.info(process.returncode)
            if process.returncode > 0:
                raise RuntimeError(stdout.read())
            subkernel = json.load(stdout)

        conn_info = subkernel["connection"]
        self.load_connection_info(conn_info)
        LOG.info(f"{self.binding.name}: connection={conn_info}")

        self.write_connection_file()

        return LocalKernelProxy(subkernel["pid"])


class LocalKernelProxy(KernelProxy):
    def __init__(self, pid):
        self.pid = pid

    def send_signal(self, signum):
        try:
            os.kill(self.pid, signum)
            return 0
        except:
            return -1
