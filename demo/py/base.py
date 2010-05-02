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

# Base class for request handlers that sets up the basic template values.
#
# Inherit from the BaseHandler class and call GetBaseTemplateValues().

import os

from google.appengine.api import users
from google.appengine.ext import webapp

from py import constants

class BaseHandler(webapp.RequestHandler):
  def GetBaseTemplateValues(self, page_title, template_name):
    """Gets the default template values.

    Args:
      page_title: The name of the page.
      template_name: The name of the template.

    Returns:
      The (template_values, template_path) tuple.  The caller can add more
      values to the template_values dict.  The template_path may be passed
      to the template.render() method directly.  The template is expected to
      be the file name within the templates/app/ directory.

      Note that the logged in user may be retrieved from
      template_values['user'].  It returns None if user is not logged in.
    """
    user = users.get_current_user()
    if user:
      username = user.nickname()
      login_url = ''
      logout_url = users.create_logout_url(self.request.uri)
    else:
      username = None
      login_url = users.create_login_url(self.request.uri)
      logout_url = ''

    template_values = {
      'title': constants.DEFAULT_TITLE,
      'base_url': 'http://' + constants.HOME_DOMAIN,
      'username': username,
      'login_url': login_url,
      'logout_url': logout_url,
      'user': user,
      'page_title': page_title,
      }
    template_path = os.path.join(os.path.dirname(__file__),
                                 '..', 'templates', 'app', template_name)
    return (template_values, template_path)
