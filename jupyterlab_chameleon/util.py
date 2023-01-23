from typing import Optional, Tuple, List

import os
from urllib.parse import urlsplit, urlunsplit

import requests
import time

from .exception import AuthenticationError, JupyterHubNotDetected

ACCESS_TOKEN_ENDPOINT = 'tokens'


def call_jupyterhub_api(
    path: str,
    query: Optional[List[Tuple[str, str]]] = None,
    body: Optional[dict] = None,
    method: str = 'GET'
) -> dict:
    hub_api_url = os.getenv('JUPYTERHUB_API_URL')
    hub_token = os.getenv('JUPYTERHUB_API_TOKEN')

    if not (hub_api_url and hub_token):
        raise JupyterHubNotDetected('Missing JupyterHub authentication info')

    hub_url_parsed = urlsplit(hub_api_url)
    hub_url_replaced = hub_url_parsed._replace(
        path=(f'{hub_url_parsed.path}/{path.lstrip("/")}'),
    )
    url = urlunsplit(hub_url_replaced)
    res = requests.request(
        url=url,
        method=method,
        params=query,
        json=body,
        headers={
            "authorization": f"token {hub_token}",
            "content-type": "application/json",
        }
    )
    res.raise_for_status()

    if res.content:
        return res.json()
    return {}


def jupyterhub_public_url(path: str) -> str:
    hub_public_url = os.getenv('JUPYTERHUB_PUBLIC_URL')

    if not hub_public_url:
        raise JupyterHubNotDetected('No public URL found for JupyterHub')

    return f"{hub_public_url.rstrip('/')}/{path.lstrip('/')}"


def refresh_access_token(source_ident=None) -> 'tuple[str,int]':
    """Refresh a user's access token via the JupyterHub API.

    This requires a custom handler be installed within JupyterHub; that handler
    is currently a part of the jupyterhub-chameleon PyPI package.

    Returns:
        A tuple of the new access token for the user, and its expiration time.

    Raises:
        AuthenticationError: if the access token cannot be refreshed.
    """
    res = call_jupyterhub_api(
        f"users/{os.getenv('JUPYTERHUB_USER')}", query=[('source', source_ident)])
    access_token = res.get("auth_state").get('access_token')
    expires_at = res.get("auth_state").get('expires_at')

    should_refresh = expires_at - time.time() < 120
    if not access_token or should_refresh:
        raise AuthenticationError(f'Failed to get access token: {res}')

    return access_token, expires_at


class ErrorResponder:
    def error_response(self, status=400, message='unknown error', **kwargs):
        self.set_status(status)
        self.write({
            **kwargs,
            'error': message
        })
        return self.finish()
