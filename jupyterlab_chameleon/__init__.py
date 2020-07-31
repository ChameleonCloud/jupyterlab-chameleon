import logging

from notebook.utils import url_path_join

from .package_artifact import PackageArtifactEndpoint

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
    # Prepend the base_url so that it works in a jupyterhub setting
    base_url = web_app.settings['base_url']
    base_endpoint = url_path_join(base_url, 'chameleon')
    package_endpoint = url_path_join(base_endpoint, 'package_artifact')

    handlers = [
        (package_endpoint, ZenodoUploadHandler,
            {"notebook_dir": nb_server_app.notebook_dir}),
    ]
    web_app.add_handlers('.*$', handlers)
