from notebook.base.handlers import APIHandler
from tornado import web

from .exception import AuthenticationError
from .util import ErrorResponder, jupyterhub_public_url, refresh_access_token


class HeartbeatHandler(APIHandler, ErrorResponder):
    """A handler that attempts to refresh the user's backend session.
    """
    @web.authenticated
    async def get(self):
        try:
            _, expires_at = refresh_access_token()
            self.set_status(200)
            self.write({"expires_at": expires_at})
            self.finish()
        except AuthenticationError as err:
            return self.error_response(
                status=401, message=next(iter(err.args), "Unknown error"),
                reauthenticate_link=jupyterhub_public_url('auth/refresh'))
        except Exception as err:
            self.log.error(err)
            return self.error_response(
                status=500, message='Unknown error occurred')
