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
import typing

from .base import HydraKernelProvisioner

if typing.TYPE_CHECKING:
    from typing import Any, Dict, List, Optional

LOG = logging.getLogger(__name__)


class LocalHydraKernelProvisioner(HydraKernelProvisioner):
    poll_interval = 0.1  # Checking local processes is cheap

    pid = None

    @property
    def has_process(self) -> bool:
        return self.pid is not None

    def reset(self):
        self.pid = None

    async def pre_launch(self, **kwargs: "Any") -> "Dict[str, Any]":
        kwargs = await super().pre_launch(**kwargs)
        # Override the kernel command; we need to spawn a background kernel
        # which requires using the agent wrapper.
        kwargs["cmd"] = [
            "hydra-agent",
            f"--kernel={self.binding.kernel}",
            f"--id={self.kernel_id}",
            "--debug",
        ]
        return kwargs

    async def launch_kernel(self, command: "List[str]", **kwargs):
        command = [shlex.quote(arg) for arg in command]
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
            if process.returncode > 0:
                raise RuntimeError(stdout.read())
            subkernel = json.load(stdout)

        self.pid = subkernel["pid"]
        conn_info = subkernel["connection"]

        LOG.info(f"{self.binding.name}: connection={conn_info}")

        return conn_info

    async def send_signal(self, signum: int) -> None:
        try:
            LOG.debug(f"kill -{signum} {self.pid}")
            os.kill(self.pid, signum)
        except ProcessLookupError:
            self.reset()

    async def poll(self) -> "Optional[int]":
        try:
            os.kill(self.pid, 0)
        except OSError:
            return -1
