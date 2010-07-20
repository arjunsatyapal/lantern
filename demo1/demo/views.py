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
import difflib
import email  # see incoming_mail()
import email.utils
import itertools
import logging
import md5
import os
import random
import re
import urllib
import urlparse
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
# import forms
import library
import models
import settings

# Add our own template library.
_library_name = __name__.rsplit('.', 1)[0] + '.library'
if not django.template.libraries.get(_library_name, None):
  django.template.add_to_builtins(_library_name)


# ## Constants # ##


IS_DEV = os.environ['SERVER_SOFTWARE'].startswith('Dev')  # Development server


# ## Exceptions # ##


class InvalidIncomingEmailError(Exception):
  """Exception raised by incoming mail handler when a problem occurs."""


# ## Helper functions # ##


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
 # initialize(request)
  if params is None:
    params = {}
  must_choose_nickname = False
  if request.user is not None:
    account = models.Account.current_user_account
    must_choose_nickname = not account.user_has_selected_nickname()
  params['title'] = constants.DEFAULT_TITLE
  params['base_url'] = ''
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


# ## Decorators for request handlers # ##


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

# ## Helper function (move eventually to library?) # ##

def collect_data_from_query(request):
  """Collects POST data passed in edit form and maps data in required
  dictionary format.

  TODO(mukundjha): Take care of other parameters like tags, commit_message etc.
  Define hard-coded constants like 'doc_title' in separate file.

  """
  data_dict = {}
  data_dict['doc_title'] = request.POST.get('doc_title')
  data_dict['trunk_id'] = request.POST.get('trunk_id')
  data_dict['doc_id'] = request.POST.get('doc_id')
  data_dict['doc_grade_level'] = int(request.POST.get('doc_grade_level',
    constants.DEFAULT_GRADE_LEVEL))

  content_data_vals = request.POST.getlist('data_val')
  content_data_types = request.POST.getlist('data_type')

  content_list = data_dict.setdefault('doc_contents', [])
  for obj_type, data_val in zip(content_data_types, content_data_vals):
    content_list.append({
        'obj_type': obj_type,
        'val': data_val,
        })
  return data_dict


def create_doc(data_dict):
  """Create new document from data passed in dictionary format.

  TODO(mukundjha): Currently works only rich text and video objects,
    extend for other objects.
  TODO(mukundjha): Replace content addition if-else block with more generic
    function.
  TODO(mukundjha): Validate url provided in link object.
  TODO(mukundjha): Move this function into another (content_manager.py) module.
  """
  trunk = data_dict.get('trunk_id')
  try:
    doc = library.create_new_doc(trunk)
  except (models.InvalidDocumentError, models.InvalidTrunkError):
    logging.exception("Error while creating a new document")
    return None

  doc.title = data_dict.get('doc_title', 'Add a title')
  doc.grade_level = data_dict.get('doc_grade_level',
    constants.DEFAULT_GRADE_LEVEL)

  for element in data_dict['doc_contents']:
    if element.get('obj_type') == 'rich_text':
      rich_text_object = library.insert_with_new_key(models.RichTextModel)
      rich_text_object.data= db.Blob(str(element.get('val')))
      rich_text_object.put()
      doc.content.append(rich_text_object.key())

    elif element.get('obj_type') == 'video':
      video_object = library.insert_with_new_key(models.VideoModel)
      video_object.video_id = str(element.get('val'))
      video_object.put()
      doc.content.append(video_object.key())

    elif element.get('obj_type') == 'doc_link':
      link = urlparse.urlparse(element.get('val'))
      if link.query:
        params = dict([query.split('=') for query in link.query.split('&')])

        referred_doc = db.get(params.get('doc_id'))
        referred_trunk = db.get(params.get('trunk_id'))

        doc_link_object = library.insert_with_new_key(models.DocLinkModel,
          trunk_ref=referred_trunk.key(), doc_ref=referred_doc.key(),
          default_title=referred_doc.title, from_trunk_ref=doc.trunk_ref.key(),
          from_doc_ref=doc.key())
        doc.content.append(doc_link_object.key())

  doc.put()
  return doc

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
    data_dict = {'errorMsg': 'Invalid Type passed to content_handler'}

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


def list_docs(request):
  """Presents a list of existing document/module in the datastore.

  List is reverse sorted by creation date and includes all the documents.
  TODO(mukundjha): Move this function to another module.
  """
  doc_list = []
  seen = {}
  for doc in models.DocModel.all():
    t = doc.trunk_ref
    k = t.key()
    if k not in seen:
      seen[k] = t.head
      d = db.get(t.head)
      doc_list.append({
          'doc': d,
          'trunk_id': str(k),
          'doc_id': str(d.key()),
          })
  return respond(request, constants.DEFAULT_TITLE, "list.html",
        {'data': doc_list})


def edit(request):
  """For editing and creating content.

  TODO(mukundjha): Split creation of new doc from editing existing.
  """
  trunk_id = request.GET.get('trunk_id')
  doc_id = request.GET.get('doc_id')

  if not trunk_id:
    doc = models.DocModel()
    return respond(request, 'Edit', 'edit.html',
      {'doc': doc, 'data_valid_range': constants.VALID_GRADE_RANGE})

  try:
    doc = library.fetch_doc(trunk_id, doc_id)
  except (models.InvalidTrunkError, models.InvalidDocumentError):
    return HttpResponse("No such document exists", status=404)

  doc_contents = library.get_doc_contents(doc)

  return respond(request, constants.DEFAULT_TITLE, "edit.html",
                {'doc': doc,
                'doc_contents': doc_contents,
                'data_valid_range': constants.VALID_GRADE_RANGE,
                'doc_id': str(doc.key()),
                'trunk_id': str(doc.trunk_ref.key())
                })


def view_doc(request):
  """Displays document from provided trunk and doc ids.

  NOTE(mukundjha): If paramater 'absolute' is passed in the request, user
    is shown the document pointed to by the doc id (or latest if only trunk
    id is passed) and does not take into account user's view histroy. This
    is useful in many cases like migrating to latest version, saving an edit
    etc.
  TODO(mukundjha): Merge with /(root) and handle other types in template
  TODO(mukundjha): Display parent title instead of up_link
  TODO(mukundjha): Maintain consistent back/parent link, currently it
   breaks after one.
  """
  trunk_id = request.GET.get('trunk_id')
  doc_id = request.GET.get('doc_id')
  parent_trunk = request.GET.get('parent_trunk')
  absolute_address_mapping = request.GET.get('absolute')

  try:
    if absolute_address_mapping:
      doc = library.fetch_doc(trunk_id, doc_id)
    else:
      doc = library.get_doc_for_user(trunk_id, users.get_current_user())

  except (models.InvalidTrunkError, models.InvalidDocumentError):
    return HttpResponse("No such document exists", status=404)

  if not parent_trunk:
    parent = library.get_parent(doc)
    if parent:
      parent_trunk = parent.trunk_ref.key()

  doc_contents = library.get_doc_contents(doc)
  doc_score = library.get_accumulated_score(doc, doc_contents,
                                            users.get_current_user())
  trunk = doc.trunk_ref

  # Just place holders to check the output, should present in better way.
  menu_items = [
    '<a href="/edit">Create New </a>',
    '<a href="/edit?trunk_id=%s&doc_id=%s">Edit this page</a>' %
    (trunk.key(), doc.key()),
    '<a href="/view?trunk_id=%s&absolute=True">Show latest</a>' %
    (trunk.key(),),
    '<a href="/history?trunk_id=%s">History</a>' %
    (trunk.key()),
    ]

  main_menu = ' | '.join(menu_items)
  title_items = [
    constants.DEFAULT_TITLE,
    ' | <b>Progress: %s</b>' % (doc_score)
    ]

  if parent_trunk:
    title_items.append('|'+'<a href="/view?trunk_id=%s">UP</a>' %(parent_trunk))

  title = ''.join(title_items)
  return respond(request, title, "view.html",
                {'doc': doc,
                'doc_score': doc_score,
                'doc_contents': doc_contents,
                'mainmenu': main_menu
                })


def history(request):
  """Show revisions of a given trunk"""
  trunk_id = request.GET.get('trunk_id')
  trunk = db.get(trunk_id)
  data = []
  revs = [i.obj_ref
          for i in models.TrunkRevisionModel.all().ancestor(trunk).order('-created')]
  for it, previous in itertools.izip(revs, revs[1:] + [None]):
    datum = {
        'doc': db.get(it),
        'previous': previous,
    }
    data.append(datum)

  return respond(request, constants.DEFAULT_TITLE,
                 "history.html", {
      'trunk_id': trunk_id,
      'data': data,
      })


def changes(request):
  """Show differences between pre and post"""
  trunk_id = request.GET.get('trunk_id')
  pre_image = db.get(request.GET.get('pre')).asText().split("\n")
  post_image = db.get(request.GET.get('post')).asText().split("\n")
  differ = difflib.HtmlDiff()
  text = differ.make_table(pre_image, post_image,
                           fromdesc="Previous",
                           todesc="This version",
                           context=True)

  return respond(
      request, constants.DEFAULT_TITLE, "changes.html",
      {
          'trunk_id': trunk_id,
          'text': text,
      })


def submit_edits(request):
  """ Accepts edits from user and stores in datastore.

  TODO(mukundjha): use AJAX/JSON
  """
  data_dict = collect_data_from_query(request)
  doc = create_doc(data_dict)
  if not doc:
    return HttpResponse("Error in creating document", status=404)
  else:
    # redirect to view mode
    trunk_id = doc.trunk_ref.key()
    doc_id = doc.key()
    return HttpResponseRedirect('/view?trunk_id=%s&doc_id=%s&absolute=True' % (trunk_id, doc_id))

	
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
                        '(its content doesn\'t matter).', status=404)
  return HttpResponse(models.Account.current_user_account.get_xsrf_token(),
                      mimetype='text/plain')
