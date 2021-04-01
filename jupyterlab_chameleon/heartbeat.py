from keystoneauth1.exceptions import Unauthorized
from jupyter_server.base.handlers import APIHandler
from tornado import web

from .exception import AuthenticationError
from .util import ErrorResponder, jupyterhub_public_url, refresh_access_token


class HeartbeatHandler(APIHandler, ErrorResponder):
    """A handler that attempts to refresh the user's backend session.
    """
    @web.authenticated
    async def get(self):
        try:
            _, expires_at = refresh_access_token(source_ident="heartbeat")
            self.set_status(200)
            self.write({"expires_at": expires_at})
            self.finish()
        except (AuthenticationError, Unauthorized) as err:
            try:
                reauthenticate_link = jupyterhub_public_url('auth/refresh')
            except Exception as _err:
                self.log.error(_err)
                reauthenticate_link = None
            return self.error_response(
                status=401, message=next(iter(err.args), "Unknown error"),
                reauthenticate_link=reauthenticate_link)
        except Exception as err:
            self.log.error(err)
            return self.error_response(
                status=500, message='Unknown error occurred')
