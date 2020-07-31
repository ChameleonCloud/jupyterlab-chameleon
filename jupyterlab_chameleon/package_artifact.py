import json
import logging
import os
import requests

from notebook.base.handlers import APIHandler
from tornado import gen, web

from .util import make_archive, upload_archive, get_auth_info

LOG = logging.getLogger(__name__)


class PackageArtifactHandler(APIHandler):
    @web.authenticated
    @gen.coroutine
    def post(self, path='', notebook_dir=None):
        self.check_xsrf_cookie()

        try:
            body = json.loads(self.request.body.decode('utf-8'))
            path = body.get('path', '.')
            if not path.startswith('/'):
                path = os.path.join(self.notebook_dir, path)

            archive = make_archive(path)
            auth_info = get_auth_info()
            artifact_id = upload_archive(archive, auth_info)
        except Exception:
            LOG.exception('There was an error!')
            self.return_error('Something went wrong')
        else:
            self.set_status(201)
            self.write(dict(artifact_id=artifact_id))
            self.finish()
