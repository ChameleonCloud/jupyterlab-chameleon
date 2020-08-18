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


def default_keystone_session_factory():
    """Obtain authentication credentials for the Swift service.

    Returns:
        keystoneauth1.session.Session: a KSA session object, which can be used
            to authenticate the Swift client.
    """
    res = call_jupyterhub_api('share/publish_token')
    auth_url = res.get('auth_url')
    token = res.get('token')
    trust_id = res.get('trust_id')
    if not (auth_url and token and trust_id):
        raise AuthenticationError('Failed to retrieve publish token')
    auth = v3.Token(auth_url=auth_url, token=token, trust_id=trust_id)
    return Session(auth=auth)


class PackageArtifactConfig(Configurable):
    """Configuration for the PackageArtifactHandler.

    """
    # TODO(jason): change to Callable when that trait is in some published
    # trailets release. It is still not being published as part of 4.x[1]
    # [1]: https://github.com/ipython/traitlets/pull/333#issuecomment-639153911
    keystone_session_factory = Any(config=True,
        default_value=default_keystone_session_factory,
        help='A ')

    ignored_file_pattern = CRegExp(config=True,
        default_value=r"(\.ipynb_checkpoints|\.git|\.ssh)/.*$",
        help=' ')

    swift_container = Unicode(config=True, default_value='trovi',
        help=' ')


class Archiver:
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
            PermissionError: on file permission errors encountered
            FileNotFoundError: if the input path does not exist
        """
        def should_include(file):
            return not self.config.ignored_file_pattern.search(file)

        temp_dir = tempfile.mkdtemp()
        archive = os.path.join(temp_dir, f'{os.path.basename(path)}.zip')

        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if os.path.isfile(path) and should_include(path):
                zipf.write(path)
            elif os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for f in files:
                        absfile = os.path.join(root, f)
                        if should_include(absfile):
                            zipf.write(absfile)

        self.log.info(f'Exported archive of {path} at {archive}')

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
            keystoneauth1.ClientException: if an error occurs when uploading to
                Swift.
        """
        session = self.config.keystone_session_factory()
        conn = Connection(session=session, os_options={
            'region_name': os.getenv('OS_REGION_NAME'),
        })

        h = hashlib.blake2b(digest_size=16)
        h.update(session.get_token().encode('utf-8'))
        h.update(path.encode('utf-8'))
        artifact_id = h.hexdigest()

        stat = os.stat(path)
        size_mb = stat.st_size / 1024 / 1024
        self.log.info((
            f'Uploading {path} ({size_mb:.2f}MB) to Swift '
            f'as {artifact_id}'))

        with open(path, 'rb') as f:
            conn.put_object(
                self.config.swift_container,
                artifact_id,
                contents=f,
                content_type=self.MIME_TYPE,
            )

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
