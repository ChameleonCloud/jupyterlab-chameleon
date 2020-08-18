import os
import requests

from .exception import AuthenticationError

ACCESS_TOKEN_ENDPOINT = 'tokens'


def call_jupyterhub_api(path, method='GET'):
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


def refresh_access_token():
    """Refresh a user's access token via the JupyterHub API.

    This requires a custom handler be installed within JupyterHub; that handler
    is currently a part of the jupyterhub-chameleon PyPI package.

    Returns:
        str: the new access token for the user.

    Raises:
        AuthenticationError: if the access token cannot be refreshed.
    """
    res = call_jupyterhub_api(ACCESS_TOKEN_ENDPOINT)
    access_token = res.get('access_token')

    if not access_token:
        raise AuthenticationError(f'Failed to get access token: {res}')

    return access_token
