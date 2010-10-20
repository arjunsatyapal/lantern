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

from demo import upload


class ImportVideos(webapp.RequestHandler):
  """Task to import videos.

  The payload is expected to have a JSON encoded list of
  (tags, title, video_uri) tuples.
  """
  def post(self):
    logging.info('=======ImportVideos')
    response = []
    videos_json  = self.request.body
    videos = simplejson.loads(videos_json)
    response = upload.import_videos(videos)
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
