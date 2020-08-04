import os
import requests

from .exception import AuthenticationError

ACCESS_TOKEN_ENDPOINT = 'tokens'


def refresh_access_token():
    """Refresh a user's access token via the JupyterHub API.

    This requires a custom handler be installed within JupyterHub; that handler
    is currently a part of the jupyterhub-chameleon PyPI package.

    Returns:
        str: the new access token for the user.

    Raises:
        AuthenticationError: if the access token cannot be refreshed.
    """
    hub_api_url = os.getenv('JUPYTERHUB_API_URL')
    hub_token = os.getenv('JUPYTERHUB_API_TOKEN')

    if not (hub_api_url and hub_token):
        raise AuthenticationError('Missing JupyterHub authentication info')

    res = requests.get(f'{hub_api_url}/{ACCESS_TOKEN_ENDPOINT}',
        headers={'authorization': f'token {hub_token}'})
    access_token = res.json().get('access_token')

    if not access_token:
        raise AuthenticationError(f'Failed to get access token: {res}')

    return access_token
