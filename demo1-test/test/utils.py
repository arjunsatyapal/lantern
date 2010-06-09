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

# Based on:
#  http://groups.google.com/group/google-appengine/msg/9132b44026040498

"""Test utils for setting up and tearing down environment.

These are not needed when using the GAE Unit's test runner, since it is
basically doing this already.
"""

# Python imports
import os
import time

# AppEngine imports
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_file_stub
from google.appengine.api import mail_stub
from google.appengine.api import urlfetch_stub
from google.appengine.api import user_service_stub

APP_ID = u'test_app'
AUTH_DOMAIN = 'gmail.com'
LOGGED_IN_USER = 't...@example.com'  # set to '' for no logged in user


def setUpTest(app_id, auth_domain='gmail.com',
              logged_in_user='test@example.com'):
  """Call from setUp() to re-initialize all stubs for each test.

  This effectively creates a new (empty) in-memory datastore.

  Args:
    app_id: The AppEngine app ID.
    auth_domain: The authentication domain. Defaults to 'gmail.com'
    logged_in_user: Set to the empty string for "none". Defaults to
        test@example.com

  Returns:
    Original apiproxy object. It should be passed back into tearDownTest()
    to reset to original state.
  """
  orig_apiproxy = apiproxy_stub_map.apiproxy
  # Ensure we're in UTC.
  os.environ['TZ'] = 'UTC'
  time.tzset()
  # Start with a fresh api proxy.
  apiproxy_stub_map.apiproxy = apiproxy_stub_map.APIProxyStubMap()
  # Use a fresh stub datastore.
  stub = datastore_file_stub.DatastoreFileStub(app_id, None)
  apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', stub)
  # Use a fresh stub UserService.
  apiproxy_stub_map.apiproxy.RegisterStub(
      'user', user_service_stub.UserServiceStub())
  os.environ['AUTH_DOMAIN'] = AUTH_DOMAIN
  os.environ['USER_EMAIL'] = LOGGED_IN_USER
  # Use a fresh urlfetch stub.
  apiproxy_stub_map.apiproxy.RegisterStub(
      'urlfetch', urlfetch_stub.URLFetchServiceStub())
  # Use a fresh mail stub.
  apiproxy_stub_map.apiproxy.RegisterStub(
      'mail', mail_stub.MailServiceStub())
  return orig_apiproxy


def tearDownTest(orig_apiproxy):
  """Call to tear down the test.

  Args:
    orig_apiproxy: The original proxy returned by setUpTest().  This will
        restore the state for the dev server.
  """
  apiproxy_stub_map.apiproxy = orig_apiproxy
