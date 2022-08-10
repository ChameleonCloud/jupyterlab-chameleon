import shutil

import json
import logging
import os
import requests
import tempfile

from jupyter_server.base.handlers import APIHandler
from keystoneauth1.exceptions.http import Unauthorized
from requests import HTTPError
from tornado import web
from traitlets import Any, Tuple
from traitlets.config import LoggingConfigurable

from .db import DB, LocalArtifact, DuplicateArtifactError
from .exception import (
    AuthenticationError,
    IllegalArchiveError,
    BadRequestError,
)
from .trovi import contents_url, get_trovi_token, artifacts_url, artifact_versions_url
from .util import ErrorResponder

LOG = logging.getLogger(__name__)


def default_prepare_upload():
    """Prepare an upload to the external storage tier.

    Returns:
        dict: a structure with the following keys:
            :url: the absolute URL to perform the upload
            :method: the request method
            :headers: any headers to include in the request
    """
    trovi_token = get_trovi_token()

    response = {
        "url": contents_url(trovi_token),
        "method": "POST",
        "headers": {
            "content-type": "application/json",
            "accept": "application/json",
        },
    }

    return response


def default_prepare_create():
    """Prepare a request for artifact creation

    Returns:
        dict: a structure with the following keys:
            :url: the absolute URL of the Trovi API
            :method: the request method
            :headers: any headers to include in the request
    """
    trovi_token = get_trovi_token()

    response = {
        "url": artifacts_url(trovi_token),
        "method": "POST",
        "headers": {
            "content-type": "application/json",
            "accepts": "application/json",
        },
    }

    return response


def default_prepare_patch(uuid):
    """Prepare a request for artifact metadata update (patch)."""
    return {
        "url": artifacts_url(get_trovi_token(), uuid=uuid),
        "method": "PATCH",
        "headers": {
            "content-type": "application/json",
            "accepts": "application/json",
        },
    }


def default_prepare_version(uuid):
    """Prepare a request for artifact creation

    Returns:
        dict: a structure with the following keys:
            :url: the absolute URL of the Trovi API
            :method: the request method
            :headers: any headers to include in the request
    """
    trovi_token = get_trovi_token()

    response = {
        "url": artifact_versions_url(trovi_token, uuid),
        "method": "POST",
        "headers": {
            "content-type": "application/json",
            "accepts": "application/json",
        },
    }

    return response


def default_prepare_list():
    """Prepare a request to retrieve all visible artifacts

    Returns:
        dict: a structure with the following keys
            :url: the absolute URL of the Trovi API
            :method: the request method
            :headers: any headers to include in the request
    """
    trovi_token = get_trovi_token()

    response = {
        "url": artifacts_url(trovi_token),
        "method": "GET",
        "headers": {
            "content-type": "application/json",
            "accepts": "application/json",
        },
    }

    return response


class ArtifactArchiver(LoggingConfigurable):
    ignored_file_pattern = Tuple(
        config=True,
        default_value=(".chameleon", ".ipynb_checkpoints", ".git", ".ssh"),
        help=(
            "A tuple of glob patterns of files/directories to ignore when packaging"
            "the archive."
        ),
    )

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

        if not os.path.isdir(path):
            raise ValueError("Input path must be a directory")

        read_dir = tempfile.mkdtemp()                    # /tmp/r
        read_base = os.path.basename(path)               # src
        write_dir = tempfile.mkdtemp()                   # /tmp/w
        write_base = os.path.join(write_dir, read_base)  # /tmp/w/src

        # Copy all the files we want to include in the archive to a temp dir.
        # We do this to filter out the ignored patterns.
        # There is no utility to ignore files with shutil.make_archive
        shutil.copytree(
            path,
            os.path.join(read_dir, read_base),
            ignore=shutil.ignore_patterns(*self.ignored_file_pattern)
        )
        # archive /tmp/r/src -> /tmp/w/src.tar.gz
        archive = shutil.make_archive(
            write_base, "gztar", root_dir=read_dir, base_dir=read_base
        )

        size_mb = os.path.getsize(archive) / 1024 / 1024
        self.log.info(
            f"Exported archive of {path} at {archive} (total {size_mb:.2f}MB)"
        )

        # Clear out the workdir copy
        shutil.rmtree(read_dir)

        return archive


class ArtifactAPIClient(LoggingConfigurable):
    # TODO(jason): change prepare_* to Callable when that trait is in some published
    # trailets release. It is still not being published as part of 4.x[1]
    # [1]: https://github.com/ipython/traitlets/pull/333#issuecomment-639153911
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

    prepare_patch = Any(
        config=True,
        default_value=default_prepare_patch,
        help=(
            "A function that prepares the artifact for patching (updating metadata.) "
            "By default this issues a patch request to Trovi's API, but custom "
            "implementations can do otherwise."
        ),
    )

    prepare_version = Any(
        config=True,
        default_value=default_prepare_version,
        help=(
            "A function that prepares a request to upload new version metadata."
            "By default this uploads to a trovi api endpoint, but custom "
            "implementations can do otherwise. the output of this function "
            "should adhere to the structure documented in "
            ":fn:`default_prepare_create`"
        ),
    )

    prepare_list = Any(
        config=True,
        default_value=default_prepare_list,
        help=(
            "A function that prepares a request to download all visible "
            "artifact metadata. "
            "By default this downloads from a trovi api endpoint, but custom "
            "implementations can do otherwise. the output of this function "
            "should adhere to the structure documented in "
            ":fn:`default_prepare_list`"
        ),
    )

    def create(self, artifact: dict) -> dict:
        if artifact_id := artifact.get("uuid"):
            prepared_req = self.prepare_version(artifact_id)
            body = self._to_version_request(artifact)
            log_message = "Created new artifact version"
        else:
            prepared_req = self.prepare_create()
            body = self._to_create_request(artifact)
            log_message = "Published new artifact"

        publish_url = prepared_req.get("url")
        publish_method = prepared_req.get("method", "POST")
        publish_headers = prepared_req.get("headers", {})

        if not publish_url:
            raise ValueError("Malformed CreateArtifact request")

        # We send the artifact on to the API without validation
        # If there's something wrong here, the API should let us know 🤞
        res = requests.request(
            url=publish_url,
            method=publish_method,
            headers=publish_headers,
            json=body,
        )
        res.raise_for_status()

        info = res.json()
        self.log.info(f"{log_message}: {json.dumps(info, indent=4)}")

        return info

    def patch(self, uuid: str, patch_list: "list[dict]") -> dict:
        prepared_req = self.prepare_patch(uuid)
        patch_url = prepared_req.get("url")
        patch_method = prepared_req.get("method", "POST")
        patch_headers = prepared_req.get("headers", {})

        if not patch_url:
            raise ValueError("Malformed patch request")

        res = requests.request(
            url=patch_url,
            method=patch_method,
            headers=patch_headers,
            json={"patch": patch_list},
        )
        res.raise_for_status()
        return res.json()

    def upload(self, path: str, mime_type: str = "application/tar+gz") -> str:
        """Upload an artifact archive file to storage.

        Args:
            path (str): the full path to the archive file.
            mime_type (str): the MIME type of the archive file. Defaults to gzipped
                tarball (application/tar+gz).

        Returns:
            a URN pointing to the uploaded contents.

        Raises:
            PermissionError: if the archive cannot be read or accessed.
            ValueError: if the prepared upload request is malformed.
            requests.exceptions.HTTPError: if the upload fails.
        """
        prepared_req = self.prepare_upload()
        upload_url = prepared_req.get("url")
        upload_method = prepared_req.get("method", "POST")
        upload_headers = prepared_req.get("headers", {})
        upload_headers.update(
            {
                "content-type": mime_type,
            }
        )

        if not upload_url:
            raise ValueError("Malformed upload request")

        stat = os.stat(path)
        size_mb = stat.st_size / 1024 / 1024
        self.log.info((f"Uploading {path} ({size_mb:.2f}MB) to {upload_url}"))

        upload_headers.update(
            {
                "content-type": mime_type,
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

        return urn

    def list(self) -> dict:
        prepared_req = self.prepare_list()
        list_url = prepared_req.get("url")
        list_method = prepared_req.get("method", "GET")
        list_headers = prepared_req.get("headers", {})

        if not list_url:
            raise ValueError("Malformed ListArtifact request")

        # TODO: support pagination / limit here, for users w/ lots of artifacts.
        res = requests.request(url=list_url, method=list_method, headers=list_headers)
        res.raise_for_status()

        artifacts = res.json().get("artifacts", [])
        self.log.info(f"Fetched {len(artifacts)} artifacts.")
        return artifacts

    def _to_version_request(self, artifact: dict):
        req = {}
        if contents := artifact.get("newContents"):
            req["contents"] = contents
        if links := artifact.get("newLinks"):
            req["links"] = links

        return req

    def _to_create_request(self, artifact: dict):
        """Converts the front-end's representation of an artifact to a valid request"""
        req = {}
        if title := artifact.get("title"):
            req["title"] = title
        if short_desc := artifact.get("short_description"):
            req["short_description"] = short_desc
        if long_desc := artifact.get("long_description"):
            req["long_description"] = long_desc
        if tags := artifact.get("tags"):
            req["tags"] = tags
        if authors := artifact.get("authors"):
            req["authors"] = authors
        if projects := artifact.get("linked_projects"):
            if not all(type(p) is dict and "urn" in p for p in projects):
                raise BadRequestError("Invalid linked projects")
            req["linked_projects"] = [p["urn"] for p in projects]
        if repro := artifact.get("reproducibility"):
            req["reproducibility"] = repro
        if owner := artifact.get("owner_urn"):
            req["owner_urn"] = owner
        if vis := artifact.get("visibility"):
            req["visibility"] = vis

        # Set the initial version as well
        if "newContents" in artifact or "newLinks" in artifact:
            req["version"] = self._to_version_request(artifact)

        return req


class ArtifactMetadataHandler(APIHandler, ErrorResponder):
    LEGACY_ID_LINK_PREFIX = "urn:trovi:artifact:chameleon:legacy:"

    def initialize(self, db: DB = None, notebook_dir: str = None):
        self.api_client = ArtifactAPIClient(config=self.config)
        self.db = db
        self.notebook_dir = notebook_dir or "."

    def _normalize_path(self, path):
        if not path.startswith("/"):
            path = os.path.join(self.notebook_dir, path)
        return os.path.normpath(path)

    @web.authenticated
    def post(self):
        """Create a new artifact, or a new version of an existing artifact."""

        self.check_xsrf_cookie()

        try:
            body = json.loads(self.request.body.decode("utf-8"))

            # 'path' is not part of the artifact metadata, but we will use it to
            # package and upload the artifact contents.
            path = body.pop("path", ".")
            path = self._normalize_path(path)
            if not path.startswith(self.notebook_dir):
                raise IllegalArchiveError(
                    "Archive source must be in notebook directory"
                )

            archive = ArtifactArchiver(config=self.config).package(path)
            contents_urn = self.api_client.upload(archive)
            body["newContents"] = {"urn": contents_urn}
            artifact = self.api_client.create(body)

            # Set local properties
            artifact["path"] = path
            artifact["ownership"] = "own"

            local_artifact = LocalArtifact(
                contents_urn, artifact["path"], None, artifact["ownership"]
            )
            try:
                self.db.insert_artifact(local_artifact)
            except DuplicateArtifactError:
                self.db.update_artifact(local_artifact)

            self.set_status(201)
            self.write(artifact)
            return self.finish()
        except (IllegalArchiveError, json.JSONDecodeError) as err:
            return self.error_response(400, str(err))
        except FileNotFoundError as err:
            return self.error_response(404, str(err))
        except PermissionError as err:
            return self.error_response(403, str(err))
        except (AuthenticationError, Unauthorized) as err:
            return self.error_response(401, str(err))
        except HTTPError as err:
            return self.error_response(
                err.response.status_code, str(err.response.content, "utf-8")
            )
        except Exception as err:
            self.log.exception("An unknown error occurred")
            return self.error_response(500, str(err))

    @web.authenticated
    def put(self):
        """Edit metadata for an existing artifact."""
        self.check_xsrf_cookie()

        try:
            body = json.loads(self.request.body.decode("utf-8"))
            uuid = body.pop("uuid")
            if not uuid:
                return self.error_response(400, "Missing UUID for artifact")

            patches = body.pop("patches")
            if not patches:
                return self.error_response(400, "Missing patches for artifact")

            artifact = self.api_client.patch(uuid, patches)
            self.set_status(200)
            self.write(artifact)
            self.finish()
        except json.JSONDecodeError as err:
            return self.error_response(400, str(err))
        except (AuthenticationError, Unauthorized) as err:
            return self.error_response(401, str(err))
        except HTTPError as err:
            return self.error_response(
                err.response.status_code, str(err.response.content, "utf-8")
            )
        except Exception as err:
            self.log.exception("An unknown error occurred")
            return self.error_response(500, str(err))

    @web.authenticated
    def get(self):
        """List all artifacts visible to the user"""
        self.check_xsrf_cookie()

        try:
            artifacts = self.api_client.list()

            # The 'id' of local artifacts == a version UUID (or ID, for legacy versions.)
            local_contents = {la.id: la.path for la in self.db.list_artifacts()}

            # Find artifacts that map to local workspace
            local_artifacts = []
            for artifact in artifacts:
                for version in artifact["versions"]:
                    search_keys = [version["contents"]["urn"]]
                    # Handle legacy-linked artifacts
                    search_keys.extend(
                        [
                            link["urn"].replace(self.LEGACY_ID_LINK_PREFIX, "")
                            for link in version["links"]
                            if link["urn"].startswith(self.LEGACY_ID_LINK_PREFIX)
                        ]
                    )

                    for key in search_keys:
                        local_path = local_contents.get(key)
                        if local_path:
                            artifact["path"] = os.path.relpath(
                                local_path, self.notebook_dir
                            ).replace("./", "")
                            artifact["ownership"] = "own"
                            local_artifacts.append(artifact)
                            break

            self.set_status(200)
            self.write({"artifacts": local_artifacts})
            return self.finish()
        except json.JSONDecodeError as err:
            return self.error_response(400, str(err))
        except (AuthenticationError, Unauthorized) as err:
            return self.error_response(401, str(err))
        except HTTPError as err:
            return self.error_response(
                err.response.status_code, str(err.response.content, "utf-8")
            )
        except Exception as err:
            self.log.exception("An Unknown error occured")
            return self.error_response(500, str(err))
