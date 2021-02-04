import os

import requests

from .exception import AuthenticationError

ACCESS_TOKEN_ENDPOINT = 'tokens'


def call_jupyterhub_api(path: str, method: str='GET') -> dict:
    hub_api_url = os.getenv('JUPYTERHUB_API_URL')
    hub_token = os.getenv('JUPYTERHUB_API_TOKEN')

    if not (hub_api_url and hub_token):
        raise AuthenticationError('Missing JupyterHub authentication info')

    res = requests.request(
        url=f'{hub_api_url}/{path}',
        method=method,
        headers={'authorization': f'token {hub_token}'})
    res.raise_for_status()

    return res.json()


def jupyterhub_public_url(path: str) -> str:
    hub_public_url = os.getenv('JUPYTERHUB_PUBLIC_URL')

    if not hub_public_url:
        raise ValueError('No public URL found for JupyterHub')

    return f"{hub_public_url.rstrip('/')}/{path.lstrip('/')}"


def refresh_access_token() -> 'tuple[str,int]':
    """Refresh a user's access token via the JupyterHub API.

    This requires a custom handler be installed within JupyterHub; that handler
    is currently a part of the jupyterhub-chameleon PyPI package.

    Returns:
        A tuple of the new access token for the user, and its expiration time.

    Raises:
        AuthenticationError: if the access token cannot be refreshed.
    """
    res = call_jupyterhub_api(ACCESS_TOKEN_ENDPOINT)
    access_token = res.get('access_token')

    if not access_token:
        raise AuthenticationError(f'Failed to get access token: {res}')

    return access_token, res.get('expires_at')


class ErrorResponder:
     def error_response(self, status=400, message='unknown error', **kwargs):
        self.set_status(status)
        self.write({
            **kwargs,
            'error': message
        })
        return self.finish()
