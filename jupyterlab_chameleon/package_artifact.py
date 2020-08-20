import argparse
import json
import hashlib
import os
import requests
import tempfile
import zipfile

from keystoneauth1.exceptions.http import Unauthorized
from keystoneauth1.identity import v3
from keystoneauth1.session import Session
from notebook.base.handlers import APIHandler
from swiftclient import Connection
from tornado import web
from traitlets import Any, CRegExp, Unicode
from traitlets.config import Configurable

from .exception import AuthenticationError
from .util import call_jupyterhub_api, refresh_access_token

import logging
LOG = logging.getLogger(__name__)


def default_prepare_upload():
    """Prepare an upload to the external storage tier.

    Returns:
        dict: a structure with the following keys:
            :artifact_id: the pre-prepared ID of the new artifact
            :publish_endpoint: the upload endpoint parameters:
                :url: the absolute URL to perform the upload
                :method: the request method
                :headers: any headers to include in the request
    """
    return call_jupyterhub_api('share/prepare_upload')


class PackageArtifactConfig(Configurable):
    """Configuration for the PackageArtifactHandler.

    """
    # TODO(jason): change to Callable when that trait is in some published
    # trailets release. It is still not being published as part of 4.x[1]
    # [1]: https://github.com/ipython/traitlets/pull/333#issuecomment-639153911
    prepare_upload = Any(config=True,
        default_value=default_prepare_upload,
        help='A ')

    ignored_file_pattern = CRegExp(config=True,
        default_value=r"(\.ipynb_checkpoints|\.git|\.ssh)/.*$",
        help=' ')

    swift_container = Unicode(config=True, default_value='trovi',
        help=' ')


class Archiver:
    MAX_ARCHIVE_SIZE = 1024 * 1024 * 100  # 100MB
    MIME_TYPE = 'application/zip'

    def __init__(self, config: 'PackageArtifactConfig', log=None):
        self.config = config
        self.log = log or logging.getLogger(__name__)

    def package(self, path: str) -> str:
        """Create zip file filename from directory

        Args:
            path (str): absolute path to directory to be zipped.
            config (PackageArtifactConfig): the configuration

        Returns:
            str: absolute path to temporary archive file.

        Raises:
            ValueError: if the input path is not a directory
            ValueError: if the total size of all files in the directory exceeds
                a maximum threshold
            PermissionError: on file permission errors encountered
            FileNotFoundError: if the input path does not exist
        """
        def should_include(file):
            return not self.config.ignored_file_pattern.search(file)

        if not os.path.isdir(path):
            raise ValueError('Input path must be a directory')

        temp_dir = tempfile.mkdtemp()
        archive = os.path.join(temp_dir, f'{os.path.basename(path)}.zip')
        total_size = 0

        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(path):
                for f in files:
                    absfile = os.path.join(root, f)
                    if not should_include(absfile):
                        continue
                    if not os.path.islink(absfile):
                        total_size += os.path.getsize(absfile)
                        if total_size > self.MAX_ARCHIVE_SIZE:
                            raise ValueError('Exceeded max archive size')
                    # Remove leading path information
                    zipf.write(absfile, arcname=absfile.replace(path, ''))

        size_mb = total_size / 1024 / 1024
        self.log.info(
            f'Exported archive of {path} at {archive} (total {size_mb:.2f}MB)')

        return archive

    def publish(self, path: str) -> str:
        """Upload an artifact archive to Swift.

        Args:
            path (str): the full path to the archive file.

        Returns:
            str: the ID of the uploaded artifact, which corresponds to the object
                name in the Swift container.

        Raises:
            PermissionError: if the archive cannot be read or accessed.
            ValueError: if the prepared upload request is malformed.
            requests.exceptions.HTTPError: if the upload fails.
        """
        upload = self.config.prepare_upload()
        artifact_id = upload.get('artifact_id')
        publish_endpoint = upload.get('publish_endpoint', {})
        publish_url = publish_endpoint.get('url')
        publish_method = publish_endpoint.get('method', 'POST')
        publish_headers = publish_endpoint.get('headers', {})
        publish_headers.update({
            'content-type': self.MIME_TYPE,
        })

        if not (artifact_id and publish_url):
            raise ValueError('Malformed upload request')

        stat = os.stat(path)
        size_mb = stat.st_size / 1024 / 1024
        self.log.info((
            f'Uploading {path} ({size_mb:.2f}MB) to {publish_url}'))

        with open(path, 'rb') as f:
            res = requests.request(
                url=publish_url, method=publish_method, headers=publish_headers,
                data=f)
            res.raise_for_status()

        return artifact_id


class PackageArtifactHandler(APIHandler):
    def initialize(self, notebook_dir=None):
        self.handler_config = PackageArtifactConfig(config=self.config)
        self.notebook_dir = notebook_dir or '.'

    def _error_response(self, status=400, message='unknown error'):
        self.set_status(status)
        self.write(dict(error=message))
        return self.finish()

    @web.authenticated
    async def post(self):
        self.check_xsrf_cookie()

        try:
            body = json.loads(self.request.body.decode('utf-8'))
            path = body.get('path', '.')
            if not path.startswith('/'):
                path = os.path.join(self.notebook_dir, path)
            path = os.path.normpath(path)

            archiver = Archiver(self.handler_config, log=self.log)
            artifact_id = archiver.publish(archiver.package(path))

            self.set_status(200)
            self.write(dict(artifact_id=artifact_id))
            return self.finish()
        except json.JSONDecodeError as err:
            return self._error_response(400, str(err))
        except FileNotFoundError as err:
            return self._error_response(404, str(err))
        except PermissionError as err:
            return self._error_response(403, str(err))
        except (AuthenticationError, Unauthorized) as err:
            return self._error_response(401, str(err))
        except Exception as err:
            self.log.exception('An unknown error occurred')
            return self._error_response(500, str(err))
