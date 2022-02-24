import json
import logging
import os
import requests
import tarfile
import tempfile
from dataclasses import asdict
from jupyter_server.base.handlers import APIHandler
from keystoneauth1.exceptions.http import Unauthorized
from tornado import web
from traitlets import Any, CRegExp, Int
from traitlets.config import LoggingConfigurable

from .db import DB
from .exception import AuthenticationError, IllegalArchiveError
from .trovi import contents_url, get_trovi_token, artifacts_url
from .util import ErrorResponder

LOG = logging.getLogger(__name__)


class ArtifactAuthor:
    def __init__(self, full_name, email, affiliation=None):
        """
        An author of an artifact

        Attrs:
            full_name (str): the full name of the author
            affiliation (str): the institution/organization with which the author
                is affiliated
            email (str): the author's email address
        """
        self.full_name = full_name
        self.affiliation = affiliation
        self.email = email


class ArtifactVersion:
    def __init__(
        self, contents_location, contents_id, links=None, created_at=None, slug=None
    ):
        """
        A version of an artifact

        Attrs:
            contents_location (str): represents where the contents are stored
            contents_id (str): an ID which is used to look up the contents at the
                storage location
            links (list[str]): a URN which represents a link relevant to the artifact
            created_at (datetime): the time at which this version was created
            slug (str): the slug for this version's URL
        """
        self.contents_location = contents_location
        self.contents_id = contents_id
        self.links = links or []
        self.created_at = created_at
        self.slug = slug

    @property
    def contents_urn(self):
        return f"urn:{self.contents_location}:{self.contents_id}"


class Artifact:
    """A shared experiment/research artifact that can be spawned in JupyterHub.

    Attrs:
        deposition_repo (str): the name of the deposition repository (e.g.,
            "zenodo" or "chameleon")
        deposition_id (str): the ID of the deposition within the repository.
        id (str): the external Trovi ID of the artifact linked to this
            deposition. Default = None.
        tags (list[str]): a list of tags used to categorize this artifact.
        authors (list[ArtifactAuthor]): a list of the authors of this artifact
        linked_projects (list[str]): a list of URNs representing projects to which
            this artifact is linked.
        repro_enable_requests (bool): flag which allows external users to request
            to reproduce this artifact's experiment. Default = False
        repro_access_hours (int): the number of hours given to external users to
            reproduce this artifact's experiments.
        repro_requests (int): the number of reproduction requests made to this artifact
        versions (list[ArtifactVersion]): a list of all versions of this artifact
        ownership (str): the requesting user's ownership status of this
            artifact. Default = "fork".
    """

    def __init__(
        self,
        id=None,
        tags=None,
        authors=None,
        linked_projects=None,
        repro_enable_requests=False,
        repro_access_hours=None,
        repro_requests=None,
        versions=None,
    ):
        self.id = id
        self.tags = tags or []
        self.authors = authors or []
        self.linked_projects = linked_projects or []
        self.repro_enable_requests = repro_enable_requests
        self.repro_access_hours = repro_access_hours
        self.repro_requests = repro_requests
        self.versions = versions or []

        # Only the deposition information is required. Theoretically this can
        # allow importing arbitrary Zenodo DOIs or from other sources that are
        # not yet existing on Trovi.
        if not versions:
            raise ValueError("Missing artifact contents")


def default_prepare_upload():
    """Prepare an upload to the external storage tier.

    Returns:
        dict: a structure with the following keys:
            :upload_endpoint: the upload endpoint parameters:
                :url: the absolute URL to perform the upload
                :method: the request method
                :headers: any headers to include in the request
    """
    trovi_token = get_trovi_token()

    response = {
        "upload_endpoint": {
            "url": contents_url(trovi_token),
            "method": "POST",
            "headers": {
                "content-type": "application/json",
                "accept": "application/json",
            },
        },
    }

    return response


def default_prepare_create():
    """Prepare a request for artifact creation

    Returns:
        dict: a structure with the following keys:
            :publish_endpoint: the publish endpoint parameters
                :url: the absolute URL of the Trovi API
                :method: the request method
                :headers: any headers to include in the request
    """
    trovi_token = get_trovi_token()

    response = {
        "publish_endpoint": {
            "url": artifacts_url(trovi_token),
            "method": "POST",
            "headers": {
                "content-type": "application/json",
                "accepts": "application/json"
            }
        }
    }

    return response

def default_prepare_list():
    """Prepare a request to retrieve all visible artifacts

    Returns:
        dict: a structure with the following keys
            :list_endpoint: the list endpoint parameters
                :url: the absolute URL of the Trovi API
                :method: the request method
                :headers: any headers to include in the request
    """
    trovi_token = get_trovi_token()

    response = {
        "list_endpoint": {
            "url": artifacts_url(trovi_token),
            "method": "GET",
            "headers": {
                "content-type": "application/json",
                "accepts": "application/json"
            }
        }
    }

    return response


class ArtifactArchiver(LoggingConfigurable):
    # TODO(jason): change to Callable when that trait is in some published
    # trailets release. It is still not being published as part of 4.x[1]
    # [1]: https://github.com/ipython/traitlets/pull/333#issuecomment-639153911
    prepare_upload = Any(
        config=True,
        default_value=default_prepare_upload,
        help=(
            "A function that prepares the archive for upload. By default "
            "this uploads to a trovi api endpoint, but custom "
            "implementations can do otherwise. the output of this function "
            "should adhere to the structure documented in "
            ":fn:`default_prepare_upload`"
        ),
    )

    ignored_file_pattern = CRegExp(
        config=True,
        default_value=r"(\.chameleon|\.ipynb_checkpoints|\.git|\.ssh)/.*$",
        help=(
            "A regex pattern of files/directories to ignore when packaaging"
            "the archive."
        ),
    )

    max_archive_size = Int(
        config=True,
        default_value=(1024 * 1024 * 500),
        help=(
            "The maximum size of the archive, before compression. The sum of "
            "all file sizes (in bytes) in the archive must be less than this "
            "number. Defaults to 500MB."
        ),
    )

    MIME_TYPE = "application/tar+gz"

    def package(self, path: str) -> str:
        """Create gzipped tar file filename from directory

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
            raise ValueError("Input path must be a directory")

        temp_dir = tempfile.mkdtemp()
        archive = os.path.join(temp_dir, f"{os.path.basename(path)}.tar.gz")
        total_size = 0

        with tarfile.open(archive, "w:gz") as tarf:
            for root, _, files in os.walk(path):
                for f in files:
                    absfile = os.path.join(root, f)
                    if not should_include(absfile):
                        continue
                    if not os.path.islink(absfile):
                        total_size += os.path.getsize(absfile)
                        if total_size > self.max_archive_size:
                            raise ValueError("Exceeded max archive size")
                    # Remove leading path information
                    tarf.add(absfile, arcname=absfile.replace(path, ""))

        size_mb = total_size / 1024 / 1024
        self.log.info(
            f"Exported archive of {path} at {archive} (total {size_mb:.2f}MB)"
        )

        return archive

    def upload(self, path: str) -> str:
        """Upload an artifact archive to Swift via the Trovi API.

        Args:
            path (str): the full path to the archive file.

        Returns:
            str: the URN of the uploaded content, which corresponds to the object
                name in the Swift container.

        Raises:
            PermissionError: if the archive cannot be read or accessed.
            ValueError: if the prepared upload request is malformed.
            requests.exceptions.HTTPError: if the upload fails.
        """
        upload = self.prepare_upload()
        upload_endpoint = upload.get("upload_endpoint", {})
        upload_url = upload_endpoint.get("url")
        upload_method = upload_endpoint.get("method", "POST")
        upload_headers = upload_endpoint.get("headers", {})
        upload_headers.update(
            {
                "content-type": self.MIME_TYPE,
            }
        )

        if not upload_url:
            raise ValueError("Malformed upload request")

        stat = os.stat(path)
        size_mb = stat.st_size / 1024 / 1024
        self.log.info((f"Uploading {path} ({size_mb:.2f}MB) to {upload_url}"))

        upload_headers.update(
            {
                "content-type": self.MIME_TYPE,
                "content-disposition": f"attachment; filename={os.path.basename(path)}",
                "content-length": str(stat.st_size),
            }
        )

        with open(path, "rb") as f:
            res = requests.request(
                url=upload_url, method=upload_method, headers=upload_headers, data=f
            )
            res.raise_for_status()

        info = res.json()
        self.log.info(f"Uploaded content: {info}")

        urn = info["contents"]["urn"]

        return urn.split(":")[-1]


class ArtifactPublisher(LoggingConfigurable):
    prepare_create = Any(
        config=True,
        default_value=default_prepare_create,
        help=(
            "A function that prepares a request to upload artifact metadata. "
            "By default this uploads to a trovi api endpoint, but custom "
            "implementations can do otherwise. the output of this function "
            "should adhere to the structure documented in "
            ":fn:`default_prepare_create`"
        ),
    )

    prepare_list = Any(config=True, default_value=default_prepare_list, help=(
        "A function that prepares a request to download all visible artifact metadata. "
        "By default this downloads from a trovi api endpoint, but custom "
        "implementations can do otherwise. the output of this function "
        "should adhere to the structure documented in "
        ":fn:`default_prepare_list`"
    ))

    def create(self, artifact: dict) -> dict:
        publish = self.prepare_create()
        publish_endpoint = publish.get("publish_endpoint", {})
        publish_url = publish_endpoint.get("url")
        publish_method = publish_endpoint.get("method", "POST")
        publish_headers = publish_endpoint.get("headers", {})

        if not publish_url:
            raise ValueError("Malformed CreateArtifact request")

        # We send the artifact on to the API without validation
        # If there's something wrong here, the API should let us know 🤞
        res = requests.request(
            url=publish_url,
            method=publish_method,
            headers=publish_headers,
            json=artifact,
        )
        res.raise_for_status()

        info = res.json()
        self.log.info(f"Published new artifact: {json.dumps(info, indent=4)}")

        return info

    def list(self) -> dict:
        prep = self.prepare_list()
        list_endpoint = prep.get("list_endpoint", {})
        list_url = list_endpoint.get("url")
        list_method = list_endpoint.get("method", "GET")
        list_headers = list_endpoint.get("headers", {})

        if not list_url:
            raise ValueError("Malformed ListArtifact request")

        res = requests.request(url=list_url, method=list_method, headers=list_headers)
        res.raise_for_status()

        info = res.json()
        self.log.info("Fetched artifacts.")

        return info


class ArtifactContentsHandler(APIHandler, ErrorResponder):
    def initialize(self, db: DB = None, notebook_dir: str = None):
        self.db = db
        self.notebook_dir = notebook_dir or "."

    def _normalize_path(self, path):
        if not path.startswith("/"):
            path = os.path.join(self.notebook_dir, path)
        return os.path.normpath(path)

    @web.authenticated
    async def post(self):
        """Create a new artifact by triggering an upload of a target directory.

        This method only uploads the content to the storage backend. Creation of
        artifact metadata is handled in a subsequent step.
        """
        self.check_xsrf_cookie()

        try:
            body = json.loads(self.request.body.decode("utf-8"))

            path = self._normalize_path(body.get("path", "."))

            if not path.startswith(self.notebook_dir):
                raise IllegalArchiveError(
                    "Archive source must be in notebook directory"
                )

            archiver = ArtifactArchiver(config=self.config)
            contents_urn = archiver.upload(archiver.package(path))

            self.set_status(200)
            self.write({"urn": contents_urn})
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
            self.log.exception("An unknown error occurred")
            return self.error_response(500, str(err))

    @web.authenticated
    def put(self):
        """Register an uploaded artifact with its external ID, when assigned."""
        self.check_xsrf_cookie()

        self.log.warning("WE GOT A PUT FOLKS!!!!!!")

        try:
            self.set_status(204)
            return self.finish()
        except json.JSONDecodeError as err:
            return self.error_response(400, str(err))
        except Exception as err:
            self.log.exception("An unknown error occurred")
            return self.error_response(500, str(err))

    @web.authenticated
    def get(self):
        """List all known uploaded artifacts on this server."""
        self.check_xsrf_cookie()

        try:
            artifacts = [asdict(a) for a in self.db.list_artifacts()]
            self.set_status(200)
            self.write(dict(artifacts=artifacts))
            return self.finish()
        except:
            self.log.exception("An unknown error occurred")
            return self.error_response(status=500, message="Failed to list artifacts")


class ArtifactMetadataHandler(APIHandler, ErrorResponder):
    def data_received(self, chunk):
        pass

    @web.authenticated
    def post(self):
        # Create new artifact
        self.check_xsrf_cookie()

        try:
            body = json.loads(self.request.body.decode("utf-8"))

            publisher = ArtifactPublisher(config=self.config)
            artifact = publisher.create(body)

            self.set_status(201)
            self.write(artifact)
            return self.finish()
        except json.JSONDecodeError as err:
            return self.error_response(400, str(err))
        except (AuthenticationError, Unauthorized) as err:
            return self.error_response(401, str(err))
        except Exception as err:
            self.log.exception("An unknown error occurred")
            return self.error_response(500, str(err))

    @web.authenticated
    def get(self):
        """List all artifacts visible to the user"""
        self.check_xsrf_cookie()

        try:
            publisher = ArtifactPublisher(config=self.config)
            artifacts = publisher.list()

            self.set_status(200)
            self.write(artifacts)
            return self.finish()
        except json.JSONDecodeError as err:
            return self.error_response(400, str(err))
        except (AuthenticationError, Unauthorized) as err:
            return self.error_response(401, str(err))
        except Exception as err:
            self.log.exception("An Unknown error occured")
            return self.error_response(500, str(err))

