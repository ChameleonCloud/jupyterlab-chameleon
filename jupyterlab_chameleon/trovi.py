import logging
import os
import requests
from urllib.parse import urljoin

from .exception import AuthenticationError
from .util import refresh_access_token

LOG = logging.getLogger(__name__)

TROVI_URL = os.getenv("TROVI_URL")


def authenticate_trovi_url(url, trovi_token):
    req = requests.PreparedRequest()
    req.prepare_url(url, {"access_token": trovi_token["access_token"]})
    return req.url


def contents_url(trovi_token, urn=None) -> str:
    return authenticate_trovi_url(
        urljoin(TROVI_URL, f"/contents/?backend=chameleon"),
        trovi_token,
    )


def artifacts_url(trovi_token, uuid=None, version=False) -> str:
    path = "/artifacts/"
    if uuid:
        path += f"{uuid}/"
    return authenticate_trovi_url(
        urljoin(TROVI_URL, path),
        trovi_token,
    )


def artifact_versions_url(trovi_token, uuid, slug=None) -> str:
    path = f"/artifacts/{uuid}/versions/"
    if slug:
        path += f"{slug}/"
    return authenticate_trovi_url(urljoin(TROVI_URL, path), trovi_token)


def get_trovi_token():
    """
    Exchange the user's auth token for a trovi token.
    """
    trovi_resp = requests.post(
        urljoin(TROVI_URL, "/token/"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        json={
            "grant_type": "token_exchange",
            "subject_token": refresh_access_token()[0],
            "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
            "scope": "artifacts:read artifacts:write",
        },
    )

    new_trovi_token = trovi_resp.json()

    LOG.debug(f"Trovi token exchange response: {new_trovi_token}")

    if trovi_resp.status_code in (
        requests.codes.unauthorized,
        requests.codes.forbidden,
    ):
        LOG.error(f"Authentication to trovi failed: {new_trovi_token}")
        raise AuthenticationError(
            "You are not authorized to upload artifacts to Trovi via Jupyter.",
        )
    elif trovi_resp.status_code != requests.codes.created:
        LOG.error(f"Authentication to trovi failed: {new_trovi_token}")
        raise AuthenticationError(
            requests.codes.internal_server_error,
            "Unknown error authenticating to Trovi.",
        )

    return new_trovi_token
