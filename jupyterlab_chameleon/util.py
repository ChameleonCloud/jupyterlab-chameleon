import collections
import os
import re
import tempfile
import zipfile

from keystoneauth1 import session
from keystoneauth1.identity import v3
from swiftclient import Connection

import logging
LOG = logging.getLogger(__name__)

ARCHIVE_MIME_TYPE = 'application/zip'
IGNORED_FILE_PATTERN = re.compile(r"(\.ipynb_checkpoints|\.git|\.ssh)/.*$")
# TODO: put the following behind settings
SWIFT_CONTAINER = 'trovi'
KEYSTONE_AUTH_URL = 'https://chi.uc.chameleoncloud.org:5000/v3'

AuthInfo = collections.namedtuple('AuthInfo',
    ['auth_url', 'identity_provider', 'protocol', 'access_token'])


def make_archive(path: str) -> str:
    """Create zip file filename from directory

    Args:
        path (str): absolute path to directory to be zipped.

    Returns:
        str: absolute path to temporary archive file.
    """
    if not os.path.exists(path):
        raise ValueError(f'Path {path} does not exist')

    temp_dir = tempfile.mkdtemp()
    archive = os.path.join(temp_dir, f'{os.path.basename(path)}.zip')

    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zipf:
        if os.path.isfile(path) and not IGNORED_FILE_PATTERN.match(path):
            zipf.write(path)
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for f in files:
                    absfile = os.path.join(root, f)
                    if not IGNORED_FILE_PATTERN.match(absfile):
                        zipf.write(absfile)

    return archive


def upload_archive(archive_path: str, auth_info: 'AuthInfo') -> str:
    auth = v3.oidc.OidcAccessToken(**auth_info._asdict())
    sess = session.Session(auth=auth)
    conn = Connection(session=sess)

    # Create hash based on...
    artifact_id = 'foo'

    with open(archive_path, 'r') as f:
        conn.put_object(
            SWIFT_CONTAINER,
            artifact_id,
            contents=f,
            content_type=ARCHIVE_MIME_TYPE,
        )

    return artifact_id


def get_auth_info():
    hub_url = os.getenv('JUPYTERHUB_PUBLIC_URL')
    hub_token = os.getenv('JUPYTERHUB_API_TOKEN')

    if not (hub_url and hub_token):
        raise ValueError('Missing JupyterHub authentication info')

    res = requests.get(f'{hub_url}services/oauth-refresh/tokens', headers={
        'authorization': f'token {hub_token}'
    })
    access_token = res.json().get('access_token')

    if not access_token:
        LOG.debug(f'Failed to get access token: {res}')
        raise ValueError('Could not refresh access token')

    keystone_auth_url = os.getenv('OS_AUTH_URL')
    keystone_identity_provider = os.getenv('OS_IDENTITY_PROVIDER')
    keystone_protocol = os.getenv('OS_PROTOCOL')

    return AuthInfo(auth_url=keystone_auth_url,
        identity_provider=keystone_identity_provider,
        protocol=keystone_protocol, access_token=access_token)
