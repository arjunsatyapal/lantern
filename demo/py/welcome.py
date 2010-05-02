# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Demo welcome page for khan edu site.
#

import os

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

# Packages for this application
from py import base
from py import constants

class Welcome(base.BaseHandler):
  _MAIN_MENU = """
  <a href="http://www.khanacademy.org">Video Library</a> |
  <a href="/">Exercises (Requires Login)</a>
  """
  def get(self):
    template_values, template_path = self.GetBaseTemplateValues(
      "Welcome", "index.html")
    template_values['mainmenu'] = self._MAIN_MENU
    self.response.out.write(template.render(template_path, template_values))


application = webapp.WSGIApplication(
  [('/', Welcome),
   ],
  debug=True)


def main():
  run_wsgi_app(application)

if __name__ == '__main__':
  main()
