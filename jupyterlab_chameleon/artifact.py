from dataclasses import asdict
import json
import os
import tempfile
import zipfile

from keystoneauth1.exceptions.http import Unauthorized
from notebook.base.handlers import APIHandler
import requests
from tornado import web
from traitlets import Any, CRegExp, Int, Unicode
from traitlets.config import LoggingConfigurable

from .db import Artifact, DB
from .exception import AuthenticationError, BadRequestError, IllegalArchiveError
from .util import call_jupyterhub_api, ErrorResponder

import logging
LOG = logging.getLogger(__name__)


def default_prepare_upload():
    """Prepare an upload to the external storage tier.

    Returns:
        dict: a structure with the following keys:
            :deposition_id: the pre-prepared ID of the new artifact deposition
            :publish_endpoint: the upload endpoint parameters:
                :url: the absolute URL to perform the upload
                :method: the request method
                :headers: any headers to include in the request
    """
    return call_jupyterhub_api('share/prepare_upload')


class ArtifactArchiver(LoggingConfigurable):
    # TODO(jason): change to Callable when that trait is in some published
    # trailets release. It is still not being published as part of 4.x[1]
    # [1]: https://github.com/ipython/traitlets/pull/333#issuecomment-639153911
    prepare_upload = Any(config=True,
        default_value=default_prepare_upload,
        help=('A function that prepares the archive for upload. By default '
              'this delegates to a JupyterHub API endpoint, but custom '
              'implementations can do otherwise. The output of this function '
              'should adhere to the structure documented in '
              ':fn:`default_prepare_upload`'))

    ignored_file_pattern = CRegExp(config=True,
        default_value=r"(\.chameleon|\.ipynb_checkpoints|\.git|\.ssh)/.*$",
        help=('A regex pattern of files/directories to ignore when packaaging'
              'the archive.'))

    swift_container = Unicode(config=True, default_value='trovi',
        help='The name of the Swift container to upload the archive to.')

    max_archive_size = Int(config=True, default_value=(1024 * 1024 * 500),
        help=('The maximum size of the archive, before compression. The sum of '
              'all file sizes (in bytes) in the archive must be less than this '
              'number. Defaults to 500MB.'))

    MIME_TYPE = 'application/zip'

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
            return not self.ignored_file_pattern.search(file)

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
                        if total_size > self.max_archive_size:
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
        upload = self.prepare_upload()
        deposition_id = upload.get('deposition_id')
        publish_endpoint = upload.get('publish_endpoint', {})
        publish_url = publish_endpoint.get('url')
        publish_method = publish_endpoint.get('method', 'POST')
        publish_headers = publish_endpoint.get('headers', {})
        publish_headers.update({
            'content-type': self.MIME_TYPE,
        })

        if not (deposition_id and publish_url):
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

        return deposition_id


class ArtifactHandler(APIHandler, ErrorResponder):
    def initialize(self, db: DB = None, notebook_dir: str = None):
        self.db = db
        self.notebook_dir = notebook_dir or '.'

    def _normalize_path(self, path):
        if not path:
            return None
        if not path.startswith('/'):
            path = os.path.join(self.notebook_dir, path)
        return os.path.normpath(path)

    @web.authenticated
    async def post(self):
        """Create a new artifact by triggering an upload of a target directory.
        """
        self.check_xsrf_cookie()

        try:
            body = json.loads(self.request.body.decode('utf-8'))
            id = body.get('id')

            path = self._normalize_path(body.get('path', '.'))

            if not path.startswith(self.notebook_dir):
                raise IllegalArchiveError(
                    'Archive source must be in notebook directory')

            archiver = ArtifactArchiver(config=self.config)
            deposition_id = archiver.publish(archiver.package(path))

            artifact = Artifact(
                id=id, path=path.replace(f'{self.notebook_dir}', '.'),
                deposition_repo='chameleon', ownership='own')
            if id:
                LOG.info(f'Creating new version of {id}')
            else:
                self.db.insert_artifact(artifact)

            self.set_status(200)
            self.write({
                **asdict(artifact),
                'deposition_id': deposition_id
            })
            return self.finish()
        except (IllegalArchiveError, json.JSONDecodeError) as err:
            return self.error_response(400, str(err))
        except FileNotFoundError as err:
            return self.error_response(404, str(err))
        except PermissionError as err:
            return self.error_response(403, str(err))
        except (AuthenticationError, Unauthorized) as err:
            return self.error_response(401, str(err))
        except Exception as err:
            self.log.exception('An unknown error occurred')
            return self.error_response(500, str(err))

    @web.authenticated
    def put(self):
        """Register an uploaded artifact with its external ID, when assigned.
        """
        self.check_xsrf_cookie()

        try:
            body = json.loads(self.request.body.decode('utf-8'))
            artifact = Artifact(
                id=body.get('id'),
                path=(self._normalize_path(body.get('path'))
                    .replace(f'{self.notebook_dir}', '.')),
                deposition_repo=body.get('deposition_repo'),
                ownership=body.get('ownership')
            )

            if not (artifact.path and artifact.id):
                raise BadRequestError('Missing "path" or "id" arguments')

            self.db.update_artifact(artifact)
            self.set_status(204)
            return self.finish()
        except json.JSONDecodeError as err:
            return self.error_response(400, str(err))
        except Exception as err:
            self.log.exception('An unknown error occurred')
            return self.error_response(500, str(err))

    @web.authenticated
    def get(self):
        """List all known uploaded artifacts on this server.
        """
        self.check_xsrf_cookie()

        try:
            artifacts = [asdict(a) for a in self.db.list_artifacts()]
            self.set_status(200)
            self.write(dict(artifacts=artifacts))
            return self.finish()
        except:
            self.log.exception('An unknown error occurred')
            return self.error_response(status=500,
                message='Failed to list artifacts')
