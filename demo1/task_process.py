#!/usr/bin/python
#
# Copyright 2010 Google Inc.
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
#

"""Processing for Task Queue."""

import logging
import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
from google.appengine.dist import use_library
use_library('django', '1.1')

# AppEngine
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

from django.utils import simplejson

from demo import models
from demo import upload


class ImportVideos(webapp.RequestHandler):
  """Task to import videos.

  The payload is expected to have a JSON encoded dict of the form:
  {
    'creator_id': creator_id,
    'videos': [ (tags, title, video_uri), ...],
  }
  """
  def post(self):
    logging.info('=======ImportVideos')
    response = []
    payload_json  = self.request.body
    payload = simplejson.loads(payload_json)
    creator_id = payload.get('creator_id')

    account = models.Account.get_account_for_id(creator_id)
    if not account:
      logging.error('xxxxx ImportVideos Aborted: unrecognized creator id: %s',
                    creator_id)
      return
    creator = account.user
    videos = payload.get('videos')
    response = upload.import_videos(videos, creator=creator)
    logging.info('IMPORT: %r' % response)
    return '<br>'.join(response)


application = webapp.WSGIApplication([
    ('/task/importVideos', ImportVideos),
    ],
    debug=True)


def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
