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

# Copied basic structure from rietveld, espcially list of imports and
# respond()
#
#  http://code.google.com/p/rietveld
#
# TODO(vchen): Clean up imports and detemine how to keep the views to a
# manageable size.
#
#  - Split forms classes into a separate module to be imported.
#  - Determine how to use memcache and what level of information to cache.
#

"""Views for Lantern."""


### Imports ###


# Python imports
import binascii
import datetime
import email  # see incoming_mail()
import email.utils
import logging
import md5
import os
import random
import re
import urllib
from cStringIO import StringIO
from xml.etree import ElementTree

# AppEngine imports
from google.appengine.api import mail
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.api import xmpp
from google.appengine.ext import db
from google.appengine.ext.db import djangoforms
from google.appengine.runtime import DeadlineExceededError
from google.appengine.runtime.apiproxy_errors import CapabilityDisabledError

# Django imports
# TODO(guido): Don't import classes/functions directly.
from django import forms
# Import settings as django_settings to avoid name conflict with settings().
from django.conf import settings as django_settings
from django.http import HttpResponse, HttpResponseRedirect
from django.http import HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import render_to_response
import django.template
from django.template import RequestContext
from django.utils import simplejson
from django.utils.safestring import mark_safe
from django.core.urlresolvers import reverse

# Local imports
import constants
#import forms
import library
import models
import settings

# Add our own template library.
_library_name = __name__.rsplit('.', 1)[0] + '.library'
if not django.template.libraries.get(_library_name, None):
  django.template.add_to_builtins(_library_name)


### Constants ###


IS_DEV = os.environ['SERVER_SOFTWARE'].startswith('Dev')  # Development server


### Exceptions ###


class InvalidIncomingEmailError(Exception):
  """Exception raised by incoming mail handler when a problem occurs."""


### Helper functions ###


# Counter displayed (by respond()) below) on every page showing how
# many requests the current incarnation has handled, not counting
# redirects.  Rendered by templates/base.html.
counter = 0


# Helper functions to fetch student's status (per module)
# from the data store

def get_user_status(request, data_dict):
  """ Populates the parameter dict with student's module status.

  Args:
    data_dict: yaml dictionary mapped with attributes of group/collection of
      modules.
  Returns:
    dictionary with per module status info appended to the dictionary passed.
  """

  # Status only for groups
  if data_dict.get(constants.YAML_TYPE_KEY) == "group":
    
    state_list = models.gql(models.StudentState, 'WHERE student = :1', request.user)
    
    # Store all the status info in a new dictionary
    temp_dict = {} 
    for state in state_list:
      try :
        current_status = int(state.status)
      except (TypeError, ValueError):
        current_status = 0
      temp_dict[state.doc] = current_status

    # If module is present in the content, 
    # and has a status record, update it else set to zero.
    for module in data_dict.get('doc_content'):
      if module['key'] in temp_dict:
         module['rating'] = temp_dict.get(module['key'], 0)
  return data_dict
 
 
def initialize(request):
  """ Temp function to initialize datastore. 
 
  Initialize the data store with some values to experiment.
  """
    
  docList = ['AlRG3wQOBqMc2nIwjoHZZ8', 'Des7BVODdcptnOdWhsWXeK',
    'BQYVV1KayQ2xjccQgIXfP+', 'BkT/Nqi4HTkpn3qPHeV+Xx', 'CE9inaE8SU6kMS05xno8Qg',
    'DOI0PIFb+0qIAdYlswlgX6']

  docRating = [100, 80, 80, 70, 90, 80]
  
  i = 0
  for id in docList:
    doc = models.DocModel()
    doc.doc_id = id
    dKey = doc.put()
    studState = models.StudentState()
    studState.student = request.user
    studState.doc = id
    studState.status = docRating[i]
    studState.put()
    i += 1


def respond(request, page_title, template, params=None):
  """Helper to render a response, passing standard stuff to the response.

  Note that params may contain additional params needed by the supplied
  template.  This method adds standard params that are passed to all templates.

  Args:
    request: The request object.
    page_title: The per-page title.
    template: The template name; '.html' is appended automatically.
    params: A dict giving the template parameters; modified in-place.

  Returns:
    Whatever render_to_response(template, params) returns.

  Raises:
    Whatever render_to_response(template, params) raises.
  """
  global counter
  counter += 1
  initialize(request)
  if params is None:
    params = {}
  must_choose_nickname = False
  if request.user is not None:
    account = models.Account.current_user_account
    must_choose_nickname = not account.user_has_selected_nickname()
  params['title'] = constants.DEFAULT_TITLE
  params['base_url'] = "/" + constants.HOME_DOMAIN
  params['request'] = request
  params['page_title'] = page_title
  params['counter'] = counter
  params['user'] = request.user
  params['is_admin'] = request.user_is_admin
  params['is_dev'] = IS_DEV
  params['media_url'] = django_settings.MEDIA_URL
  full_path = request.get_full_path().encode('utf-8')
  if request.user is None:
    params['login_url'] = users.create_login_url(full_path)
    params['username'] = None
  else:
    params['logout_url'] = users.create_logout_url(full_path)
    params['username'] = request.user.nickname()
    account = models.Account.current_user_account
    if account is not None:
      params['xsrf_token'] = account.get_xsrf_token()
  params['must_choose_nickname'] = must_choose_nickname
  try:
    return render_to_response(os.path.join('app', template), params,
                              context_instance=RequestContext(request))
  except DeadlineExceededError:
    logging.exception('DeadlineExceededError')
    return HttpResponse('DeadlineExceededError', status=503)
  except CapabilityDisabledError, err:
    logging.exception('CapabilityDisabledError: %s', err)
    return HttpResponse('Rietveld: App Engine is undergoing maintenance. '
                        'Please try again in a while. ' + str(err),
                        status=503)
  except MemoryError:
    logging.exception('MemoryError')
    return HttpResponse('MemoryError', status=503)
  except AssertionError:
    logging.exception('AssertionError')
    return HttpResponse('AssertionError')


def _random_bytes(n):
  """Helper returning a string of random bytes of given length."""
  return ''.join(map(chr, (random.randrange(256) for i in xrange(n))))


def _clean_int(value, default, min_value=None, max_value=None):
  """Helper to cast value to int and to clip it to min or max_value.

  Args:
    value: Any value (preferably something that can be casted to int).
    default: Default value to be used when type casting fails.
    min_value: Minimum allowed value (default: None).
    max_value: Maximum allowed value (default: None).

  Returns:
    An integer between min_value and max_value.
  """
  if not isinstance(value, (int, long)):
    try:
      value = int(value)
    except (TypeError, ValueError), err:
      value = default
  if min_value is not None:
    value = max(min_value, value)
  if max_value is not None:
    value = min(value, max_value)
  return value


### Decorators for request handlers ###


def post_required(func):
  """Decorator that returns an error unless request.method == 'POST'."""

  def post_wrapper(request, *args, **kwds):
    if request.method != 'POST':
      return HttpResponse('This requires a POST request.', status=405)
    return func(request, *args, **kwds)

  return post_wrapper


def login_required(func):
  """Decorator that redirects to the login page if you're not logged in."""

  def login_wrapper(request, *args, **kwds):
    if request.user is None:
      return HttpResponseRedirect(
          users.create_login_url(request.get_full_path().encode('utf-8')))
    return func(request, *args, **kwds)

  return login_wrapper


def xsrf_required(func):
  """Decorator to check XSRF token.

  This only checks if the method is POST; it lets other method go
  through unchallenged.  Apply after @login_required and (if
  applicable) @post_required.  This decorator is mutually exclusive
  with @upload_required.
  """

  def xsrf_wrapper(request, *args, **kwds):
    if request.method == 'POST':
      post_token = request.POST.get('xsrf_token')
      if not post_token:
        return HttpResponse('Missing XSRF token.', status=403)
      account = models.Account.current_user_account
      if not account:
        return HttpResponse('Must be logged in for XSRF check.', status=403)
      xsrf_token = account.get_xsrf_token()
      if post_token != xsrf_token:
        # Try the previous hour's token
        xsrf_token = account.get_xsrf_token(-1)
        if post_token != xsrf_token:
          return HttpResponse('Invalid XSRF token.', status=403)
    return func(request, *args, **kwds)

  return xsrf_wrapper


def upload_required(func):
  """Decorator for POST requests from the upload.py script.

  Right now this is for documentation only, but eventually we should
  change this to insist on a special header that JavaScript cannot
  add, to prevent XSRF attacks on these URLs.  This decorator is
  mutually exclusive with @xsrf_required.
  """
  return func


def admin_required(func):
  """Decorator that insists that you're logged in as administratior."""

  def admin_wrapper(request, *args, **kwds):
    if request.user is None:
      return HttpResponseRedirect(
          users.create_login_url(request.get_full_path().encode('utf-8')))
    if not request.user_is_admin:
      return HttpResponseForbidden('You must be admin in for this function')
    return func(request, *args, **kwds)

  return admin_wrapper


def user_key_required(func):
  """Decorator that processes the user handler argument."""

  def user_key_wrapper(request, user_key, *args, **kwds):
    user_key = urllib.unquote(user_key)
    if '@' in user_key:
      request.user_to_show = users.User(user_key)
    else:
      account = models.Account.get_account_for_nickname(user_key)
      if not account:
        logging.info('account not found for nickname %s' % user_key)
        return HttpResponseNotFound('No user found with that key (%s)' %
                                    user_key)
      request.user_to_show = account.user
    return func(request, *args, **kwds)

  return user_key_wrapper


### Request handlers ###

def content_handler(request, title, template, file_path, node_type):
  
  """Handels request and renders template with content, based on type of data.
      
  Helper function which loads the provided template with data extracted from
  file  provided in file_path or renders an error page if error occurs.

  Args:
     request: The HTTP request object
     title: Default title for the page
     template: Template to be used to render the page
     file_path: Path to yaml file to be parsed
     node_type: String describing the type of content file (node/leaf)

  Returns: 
     Whatever render_to_response(template, params) returns if no error, else
     displays an error page.

  Raises:
     Whatever render_to_response(template, params) raises.
  """

  _MAIN_MENU = """
  <a href = "http://www.khanacademy.org">Video Library</a> |
  <a href = "/">Exercises (Requires Login)</a>
  """
  # Parse according to type
  if node_type == 'leaf':
    data_dict = library.parse_leaf(file_path)
  elif node_type == 'node':
    data_dict = library.parse_node(file_path)
  else:
    data_dict = {'errorMsg':'Invalid Type passed to content_handler'}
  
  data_dict['mainmenu'] = _MAIN_MENU
  
  if 'errorMsg' in data_dict:
    logging.error(data_dict['errorMsg'])
    return HttpResponse(data_dict['errorMsg'], status = 500)

  data_dict = get_user_status(request, data_dict)

  return respond(request, title, template, data_dict)


@login_required
def index(request):
  """/ - Show the initial page. Redirect to login page if required.

  Calls content_handler function with appropriate parameter based on parameters
  in get request
  """

  # Required parameters to render page
  doc_id = request.GET.get('docId');
  doc_type = request.GET.get('docType');

  # Initial course page
  # TODO(mukundjha) : point to correct page
 
  _INIT_PAGE = os.path.join(settings.ROOT_PATH, 'demo/content/course-template');
  _PATH_ = os.path.join(settings.ROOT_PATH, 'demo/content');

  # If doc_id is not specified, redirect to default initial page
  if not doc_id:
    # Initial page
    return content_handler(request, constants.DEFAULT_TITLE, 
      constants.GROUP_TEMPLATE, _INIT_PAGE, 'node')

  elif not doc_type:
    # Get the doc_type before redirecting to the current page.
    page_path = _INIT_PAGE
    return content_handler(request, constants.DEFAULT_TITLE, 
      constants.GROUP_TEMPLATE, _INIT_PAGE, 'node')
  
  else:
    # If group page.
    if doc_type == "g":
      # Render as group
      page_path = os.path.join(_PATH_, doc_id)
      logging.info('Rendering group page\n')
      return content_handler(request, constants.DEFAULT_TITLE, 
        constants.GROUP_TEMPLATE, page_path, 'node')
    
    # If content
    elif doc_type == "c":
      # Render as content page
      page_path = os.path.join(_PATH_, doc_id)
      return content_handler(request, constants.DEFAULT_TITLE, 
        constants.CONTENT_TEMPLATE, page_path, 'leaf')
      
    # Default page
    else:
      return content_handler(request, constants.DEFAULT_TITLE, 
        constants.GROUP_TEMPLATE, _INIT_PAGE, 'node')
	

def video(request):
  """/video - Shows video with list of other related videos."""

  # TODO(vchen): Need to convert to the CS chapter
  return respond(request, 'SUBJECT', 'video.html',
                 {})


@login_required
def xsrf_token(request):
  """/xsrf_token - Return the user's XSRF token.

  This is used by tools like git-cl that need to be able to interact with the
  site on the user's behalf.  A custom header named X-Requesting-XSRF-Token must
  be included in the HTTP request; an error is returned otherwise.

  TODO(vche): Use this to handle JS-based user-event tracking.
  """
  if not request.META.has_key('HTTP_X_REQUESTING_XSRF_TOKEN'):
    return HttpResponse('Please include a header named X-Requesting-XSRF-Token '
                        '(its content doesn\'t matter).', status=400)
  return HttpResponse(models.Account.current_user_account.get_xsrf_token(),
                      mimetype='text/plain')
