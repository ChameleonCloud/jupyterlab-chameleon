# Copyright 2021 University of Chicago
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

LOG = logging.getLogger(__name__)


class HydraException(Exception):
    _msg_fmt = "An unknown exception occurred."

    def __init__(self, message=None, **kwargs):
        if not message:
            try:
                message = self._msg_fmt % kwargs
            except Exception:
                # kwargs doesn't match a variable in self._msg_fmt
                # log the issue and the kwargs
                prs = ", ".join("%s: %s" % pair for pair in kwargs.items())
                LOG.exception(
                    f"Exception in string format operation (arguments {prs})"
                )
                # at least get the core self._msg_fmt out if something
                # happened
                message = self._msg_fmt

        super(Exception, self).__init__(message)

    def __str__(self):
        return str(self.args[0])
