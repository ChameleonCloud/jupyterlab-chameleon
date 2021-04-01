import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from jupyter_server.utils import url_path_join

from .artifact import ArtifactHandler
from .db import Artifact, DB
from .heartbeat import HeartbeatHandler
from ._version import __version__

if TYPE_CHECKING:
    from notebook.notebookapp import NotebookApp

HERE = Path(__file__).parent.resolve()

with (HERE / "labextension" / "package.json").open() as fid:
    data = json.load(fid)


def _jupyter_labextension_paths():
    return [{
        "src": "labextension",
        "dest": data["name"]
    }]


def _jupyter_server_extension_points():
    return [{
        "module": "jupyterlab_chameleon"
    }]


def _load_jupyter_server_extension(server_app: "NotebookApp"):
    """Called when the extension is loaded.

    Args:
        server_app (NotebookApp): handle to the Notebook webserver instance.
    """
    web_app = server_app.web_app
    notebook_dir = server_app.notebook_dir or "."

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

    init_db(server_app, db)
    server_app.log.info("Registered Chameleon extension at URL path /chameleon")


# For backward compatibility
load_jupyter_server_extension = _load_jupyter_server_extension


def init_db(server_app: "NotebookApp", db: "DB"):
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
        server_app.log.exception('Error initializing database')
