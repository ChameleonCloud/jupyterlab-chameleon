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
import io
import json
import operator
import os
import signal
import tarfile
import typing

from keystoneauth1 import loading
from keystoneauth1.adapter import Adapter

from .base import HydraKernelManager, KernelProxy

if typing.TYPE_CHECKING:
    from ..binding import Binding


def keystone_session():
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
    def __init__(self, session, container_uuid=None):
        self._uuid = container_uuid
        self._session = Adapter(
            session=session, service_type="container", interface="public"
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

        res = self._session.get(
            f"/containers/{self._uuid}/get_archive?path={runtime_dir}"
        )
        connection_tar_data: str = res.json()["data"]
        fd = io.BytesIO(connection_tar_data.encode("utf-8"))
        with tarfile.open(fileobj=fd, mode="r") as tar:
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

    def kill_container(self, signum=signal.SIGKILL):
        return self._session.post(f"/containers/{self._uuid}/kill?signal={int(signum)}")


class ZunHydraKernelManager(HydraKernelManager):
    def post_init(self, binding: "Binding"):
        session = keystone_session()
        self.neutron = Adapter(
            session=session,
            service_type="network",
            interface="public",
        )
        container_uuid = binding.connection.get("container_uuid")
        if not container_uuid:
            raise ValueError("Missing container UUID")
        self.zun = ZunClient(session, container_uuid=container_uuid)

    def _launch_kernel(self, kernel_cmd, **kw):
        # The connection file has already been written as part of `pre_start_kernel`,
        # but we are going to be overriding ports to the subkernel's exposed
        # ports.
        self.reset_ports()
        self.cleanup_connection_file()

        # Try to find a public IP assigned to the kernel

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
        self.load_connection_info(conn_info)

        # Rewrite connection IP to floating IP
        self.ip = container_fip["floating_ip_address"]

        self.write_connection_file()

        return ZunKernelProxy(zun_client=self.zun)


class ZunKernelProxy(KernelProxy):
    # Don't check so often that the kernel is down
    poll_interval = 30

    def __init__(self, zun_client: "ZunClient" = None) -> None:
        self.zun = zun_client

    def send_signal(self, signum):
        if signum == 0:
            # Just check if container active
            return self.zun.is_container_running()
        else:
            # Send kill signal
            self.zun.post(f"/containers/{self.container_uuid}/kill?signal={signum}")
            return True
