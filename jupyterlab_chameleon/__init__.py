import os

from notebook.utils import url_path_join

from .artifact import ArtifactHandler
from .db import Artifact, DB
from .heartbeat import HeartbeatHandler

import logging
LOG = logging.getLogger(__name__)


def _jupyter_server_extension_paths():
    return [{
        'module': 'jupyterlab_chameleon'
    }]


def load_jupyter_server_extension(nb_server_app):
    """Called when the extension is loaded.

    Args:
        nb_server_app (NotebookApp): handle to the Notebook webserver instance.
    """
    web_app = nb_server_app.web_app
    notebook_dir = nb_server_app.notebook_dir

    # Prepend the base_url so that it works in a jupyterhub setting
    base_url = web_app.settings['base_url']
    base_endpoint = url_path_join(base_url, 'chameleon')
    artifact_endpoint = url_path_join(base_endpoint, 'artifacts')
    heartbeat_endpoint = url_path_join(base_endpoint, 'heartbeat')

    db = DB(database=f'{notebook_dir}/.chameleon/chameleon.db')

    handlers = [
        (artifact_endpoint, ArtifactHandler,
            {'db': db, 'notebook_dir': notebook_dir}),
        (heartbeat_endpoint, HeartbeatHandler),
    ]
    web_app.add_handlers('.*$', handlers)

    init_db(db)


def init_db(db: DB):
    try:
        db.build_schema()
        # Also check if there is an initial artifact on the environment.
        artifact_id = os.getenv('ARTIFACT_ID')
        if artifact_id:
            # Clear any existing artifacts; this is an ephemeral artifact
            # environment and it is OK to clean up for sanity. We can't do
            # this in a "workbench" server because the user may have multiple
            # artifacts linked to their working directory persisted.
            db.reset()
            db.insert_artifact(Artifact(
                path='', id=artifact_id,
                deposition_repo=os.getenv('ARTIFACT_DEPOSITION_REPO'),
                ownership=os.getenv('ARTIFACT_OWNERSHIP'),
            ))
    except Exception:
        LOG.exception('Error initializing database')
