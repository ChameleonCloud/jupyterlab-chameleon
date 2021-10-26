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
import argparse
import asyncio
import base64
import io
import json
import logging
import operator
import os
import signal
import tarfile
import typing

from keystoneauth1 import loading
from keystoneauth1.adapter import Adapter
from traitlets.traitlets import Unicode

from .base import FileManagementMixin, HydraKernelProvisioner
from ..traitlets import EntryPointType

if typing.TYPE_CHECKING:
    from tarfile import TarFile
    from typing import Any, Dict, List, Optional

LOG = logging.getLogger(__name__)


def default_auth_provider():
    fake_argv = []
    parser = argparse.ArgumentParser()
    loading.cli.register_argparse_arguments(parser, fake_argv)
    loading.session.register_argparse_arguments(parser)
    loading.adapter.register_argparse_arguments(parser)
    args = parser.parse_args(fake_argv)
    auth = loading.cli.load_from_argparse_arguments(args)
    sess = loading.session.load_from_argparse_arguments(args, auth=auth)
    return sess


class ZunClient(object):
    RESTART_TIMEOUT = 15  # seconds

    def __init__(self, session, container_uuid=None):
        self._uuid = container_uuid
        self._session = Adapter(
            session=session,
            service_type="container",
            interface="public",
            # 1.25 - support for encode/decode archive file
            default_microversion="1.25",
        )

    def get_container(self):
        res = self._session.get(f"/containers/{self._uuid}")
        return res.json()

    def get_client_connection_info(self):
        res = self._session.post(
            f"/containers/{self._uuid}/execute?command=env&run=true"
        )
        env_output: str = res.json()["output"]
        env_lines = env_output.split("\n")

        runtime_dir = None
        for line in env_lines:
            if line.startswith("JUPYTER_RUNTIME_DIR"):
                runtime_dir = line.split("=")[1]
                break

        if not runtime_dir:
            # TODO: we can probably be more graceful here and try some sane
            # default locations or try to figure out the connection file location
            # somehow else.
            raise RuntimeError(
                "Cannot connect: container does not set JUPYTER_RUNTIME_DIR in environment"
            )

        with self.download_path(runtime_dir) as tar:
            # Sort by mtime to get the latest connection file written by the
            # container process.
            conn_files = sorted(
                [
                    tarinfo
                    for tarinfo in tar.getmembers()
                    if tarinfo.isfile()
                    and os.path.basename(tarinfo.name).startswith("kernel-")
                ],
                key=operator.attrgetter("mtime"),
                reverse=True,
            )
            if not conn_files:
                raise RuntimeError(
                    "Cannot connect: no kernel connection file found in running container"
                )
            conn_file = tar.extractfile(conn_files[0])
            return json.load(conn_file)

    def is_container_running(self):
        container = self.get_container()
        return container["status"] == "Running"

    async def restart_container(self, timeout: "int" = None):
        if timeout is None:
            timeout = self.RESTART_TIMEOUT

        self._session.post(f"/containers/{self._uuid}/reboot")

        async def _until_running():
            while not self.is_container_running():
                await asyncio.sleep(1.0)

        await asyncio.wait_for(_until_running(), float(timeout))

    def kill_container(self, signum=signal.SIGKILL):
        return self._session.post(f"/containers/{self._uuid}/kill?signal={int(signum)}")

    def download_path(self, source_path: "str") -> "TarFile":
        res = self._session.get(
            f"/containers/{self._uuid}/get_archive?path={source_path}&encode_data=True"
        )
        tar_data: str = res.json()["data"]
        fd = io.BytesIO(base64.decodebytes(tar_data.encode("utf-8")))
        return tarfile.open(fileobj=fd, mode="r")

    def upload_path(self, dest_path: "str", contents: "io.BytesIO"):
        self._session.post(
            f"/containers/{self._uuid}/put_archive?path={dest_path}&decode_data=True",
            json={"data": base64.encodebytes(contents.read()).decode("utf-8")},
        )


class ZunHydraKernelProvisioner(FileManagementMixin, HydraKernelProvisioner):
    container_uuid = Unicode()

    auth_provider = EntryPointType("hydra_kernel.zun_provisioner.auth_provider")
    _auth_provider_factory = None

    poll_interval = 5.0

    @property
    def auth_provider_factory(self):
        if not self._auth_provider_factory:
            for key, entry_point in self.auth_provider.load_entry_points().items():
                try:
                    self._auth_provider_factory = entry_point.load()
                except Exception as e:
                    self.log.debug(
                        "Failed to load %s entrypoint %r: %r",
                        self.auth_provider.entry_point_group,
                        key,
                        e,
                    )
        return self._auth_provider_factory

    @property
    def has_process(self) -> bool:
        return self.zun is not None

    async def poll(self) -> "Optional[int]":
        if not self.zun.is_container_running():
            return -1

    async def send_signal(self, signum: "int") -> None:
        self.zun.kill_container(signum)

    def _get_session(self):
        if callable(self.auth_provider_factory):
            return self.auth_provider_factory()
        else:
            return default_auth_provider()

    async def pre_launch(self, **kwargs: "Any") -> "Dict[str, Any]":
        kwargs = await super().pre_launch(**kwargs)
        session = self._get_session()
        self.neutron = Adapter(
            session=session,
            service_type="network",
            interface="public",
        )
        if not self.container_uuid:
            raise ValueError("Missing container UUID")

        self.zun = ZunClient(session, container_uuid=self.container_uuid)

        # Place some value in "cmd" even though we're not launching a kernel;
        # other code nevertheless assumes this will have some value
        kwargs["cmd"] = [
            "echo",
            "The Zun provisioner does not support the kernel 'cmd' argument.",
        ]

        # TODO: possibly attempt to start the container if it is stopped/created

        return kwargs

    async def launch_kernel(
        self, command: "List[str]", **kwargs: "Any"
    ) -> "KernelConnectionInfo":
        if not self.zun.is_container_running():
            self.binding.update_progress("Restarting container")
            await self.zun.restart_container()

        self.binding.update_progress("Checking container")
        container = self.zun.get_container()
        container_ports = [
            addr["port"]
            for network_id, addrs in container["addresses"].items()
            for addr in addrs
        ]
        active_fips = self.neutron.get(f"/v2.0/floatingips?status=ACTIVE").json()[
            "floatingips"
        ]
        container_fip = next(
            iter([fip for fip in active_fips if fip["port_id"] in container_ports]),
            None,
        )
        if not container_fip:
            raise RuntimeError(
                f"Cannot connect: container {container['uuid']} has no Floating IP attached"
            )

        # Read kernel connection file
        conn_info = self.zun.get_client_connection_info()
        conn_info["ip"] = container_fip["floating_ip_address"]
        self.binding.update_progress("Ready")

        return conn_info

    def get_shutdown_wait_time(self, recommended: float = 5) -> float:
        # Allow containers to take upwards of 30 seconds to tear down
        return max(recommended, 30.0)

    async def upload_path(self, local_path: "str", remote_path: "str" = None):
        self.binding.update_progress("Preparing upload")
        fd = self.prepare_upload(local_path)
        self.binding.update_progress("Uploading")
        self.zun.upload_path(remote_path, fd)

    async def download_path(self, remote_path: "str", local_path: "str" = None):
        self.binding.update_progress("Downloading")
        with self.zun.download_path(remote_path) as tar:
            tar.extractall(local_path)
