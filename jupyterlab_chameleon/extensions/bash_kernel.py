import os

from ..util import refresh_access_token


def refresh_access_token_task():
    """Refresh the OS_ACCESS_TOKEN environment variable periodically.

    This is necessary because access tokens generated by Keycloak have a
    relatively short lifetime.
    """
    def task_fn():
        access_token, _ = refresh_access_token(source_ident="bash_kernel")
        os.environ['OS_ACCESS_TOKEN'] = access_token

    return task_fn, {'interval_s': 120}
