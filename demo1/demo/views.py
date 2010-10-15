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
from common import subjects
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


class UnknownContentTypeError(Exception):
  """Raised when create_doc() is asked to create unknown type of document."""

# ## Helper functions # ##


# Counter displayed (by respond()) below) on every page showing how
# many requests the current incarnation has handled, not counting
# redirects.  Rendered by templates/base.html.
counter = 0

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
  data_dict['doc_label'] = request.POST.get('doc_label')
  data_dict['doc_grade_level'] = int(request.POST.get('doc_grade_level',
                                     constants.DEFAULT_GRADE_LEVEL))
  data_dict['doc_tags'] = request.POST.get('doc_tags')
  content_data_vals = request.POST.getlist('data_val')
  content_data_types = request.POST.getlist('data_type')
  content_height = request.POST.getlist('data_height')
  content_width = request.POST.getlist('data_width')
  content_title = request.POST.getlist('data_title')
  content_is_shared = request.POST.getlist('data_is_shared')

  content_list = data_dict.setdefault('doc_contents', [])
  for obj_type, data_val, height, width, title, is_shared in zip(
      content_data_types, content_data_vals, content_height, content_width,
      content_title, content_is_shared):
    content_list.append({
        'obj_type': obj_type,
        'val': data_val,
        'height': height,
        'width': width,
        'title': title,
        'is_shared': is_shared,
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
  TODO(mukundjha): Move insertion (hashing) to model specific method?
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
  doc.label = data_dict.get('doc_label', models.AllowedLabels.MODULE)
  tags = data_dict.get('doc_tags')

  # Tags are separated by commas (spaces and tabs are removed)
  tag_separator = re.compile('[ \t]*,[ \t]*')
  starting_space = re.compile('^[ \t]+')  # Spaces in begining of a tag
  ending_space = re.compile('[ \t]+$')  # Spaces at end of the tag

  if tags:
    tags = starting_space.sub('', tags)
    tags = ending_space.sub('', tags)
    tag_list = tag_separator.split(tags)
    doc.tags = [db.Category(tag) for tag in tag_list]
  else:
    doc.tags = []
  doc.score_weight = [1.0]

  # Tracks the number of occurrences of the same widget with the same title
  # Keys are (widget_url, title) tuples.
  widget_index_map = {}
  for element in data_dict['doc_contents']:

    if element.get('obj_type') == 'rich_text':
      text = element.get('val').encode('utf-8')
      object = models.RichTextModel.insert(data=text)
      doc.content.append(object.key())

    elif element.get('obj_type') == 'video':
      video_id = str(element.get('val'))
      title = str(element.get('title'))
      height = str(element.get('height'))
      width = str(element.get('width'))
      object = models.VideoModel.insert(video_id=video_id, width=width,
                                        height=height, title=title)
      doc.content.append(object.key())

    elif element.get('obj_type') == 'doc_link':
      link = urlparse.urlparse(element.get('val'))
      if link.query:
        params = dict([query.split('=') for query in link.query.split('&')])

        referred_doc = db.get(params.get('doc_id'))
        referred_trunk = db.get(params.get('trunk_id'))

        doc_link_object = models.DocLinkModel.insert(
            trunk_ref=referred_trunk.key(), doc_ref=referred_doc.key(),
            default_title=referred_doc.title, from_trunk_ref=doc.trunk_ref.key(),
            from_doc_ref=doc.key())

        doc.content.append(doc_link_object.key())

    elif element.get('obj_type') == 'widget':
      widget_url = str(element.get('val'))
      title = str(element.get('title'))
      height = str(element.get('height'))
      width = str(element.get('width'))

      is_shared_str = element.get('is_shared', 'True')
      is_shared = True
      if is_shared_str.lower() in ('0', 'false'):
        is_shared = False

      if is_shared:
        widget_object = models.WidgetModel.insert(
            widget_url=widget_url, height=height, width=width, title=title,
            is_shared=is_shared)
      else:
        # Determine how many times the same (widget, title) has appeared on
        # the page
        index_key = (widget_url, title)
        widget_index = widget_index_map.setdefault(index_key, 0)
        widget_index_map[index_key] += 1

        widget_object = models.WidgetModel.insert(
            widget_url=widget_url, height=height, width=width, title=title,
            is_shared=is_shared, widget_index=widget_index, trunk_id=trunk)
      doc.content.append(widget_object.key())

    elif element.get('obj_type') == 'notepad':
      try:
        key = element.get('val')
        object = db.get(key)
      except db.BadKeyError:
        object = None
      if not object:
        object = models.NotePadModel.insert_with_new_key()
      doc.content.append(object.key())

    else:
      raise UnknownContentTypeError("What kind of object is that??? %r" % element)

  doc.put()

  # If we are at the tip of a trunk, we would need to update cached data.
  trunk = doc.trunk_ref
  if trunk.head == str(doc.key()):
    trunk.setHead(str(doc.key()))
    trunk.put()

  return doc

### Request handlers ###

@login_required
def index(request):
  """/ - Show the initial Homepage. Redirect to login page if required.
  """
  # Recently finished pages.
  recently_finished = models.DocVisitState.all().filter(
      'user =', users.get_current_user()).filter(
      'progress_score =', 100).order('-last_visit').fetch(5)

  # Fetching the latest version
  for entry in recently_finished:
    entry.doc = library.fetch_doc(entry.trunk_ref.key())
    doc_path_entry = models.TraversalPath.all().filter(
      'current_trunk =', entry.trunk_ref).filter(
      'user =', users.get_current_user()).get()
    if doc_path_entry:
      entry.path = library.expand_path(doc_path_entry.path, False, False,
                                       users.get_current_user())
    else:
      entry.path = []


  # Course title is stale here
  in_progress_courses = library.get_recent_in_progress_courses(
      users.get_current_user())
  return respond(request, constants.DEFAULT_TITLE, "homepage.html",
                 {'recently_finished': recently_finished,
                 'in_progress_courses': in_progress_courses})


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


def _ReadTemplate(template):
  """Reads and returns the contents of the specified template.

  Templates are read  from the templates/include directory.

  Args:
    template: The base name of the template file.
  """
  f = open(os.path.join('templates', 'include', template), 'r')
  try:
    return f.read()
  finally:
    f.close()


# Lazily created global instance of template strings to be published to the
# client.
_edit_templates = {}


def _GetEditTemplates():
  """Returns a new dict of templates to be returnted to the client."""
  global _edit_templates

  if not _edit_templates:
    templates = (
        ('template_preamble', 'edit_preamble.html'),
        ('template_doc_link', 'edit_doc_link_model.html'),
        ('template_rich_text', 'edit_rich_text_model.html'),
        ('template_widget', 'edit_widget_model.html'),
        ('template_notepad', 'edit_notepad_model.html'),
        ('template_video', 'edit_video_model.html'),
        )
    for key, fname in templates:
      template = _ReadTemplate(fname)
      template = template.replace('|get_key', '.key')
      _edit_templates[key] = simplejson.dumps(template)
  return _edit_templates.copy()


def edit(request):
  """For editing and creating content.

  TODO(mukundjha): Split creation of new doc from editing existing.
  """
  trunk_id = request.GET.get('trunk_id')
  doc_id = request.GET.get('doc_id')

  render_dict = _GetEditTemplates()

  if not trunk_id:
    doc = models.DocModel()
    render_dict.update(
        {'doc': doc,
         'data_valid_range': constants.VALID_GRADE_RANGE,
         'allowed_labels': models.AllowedLabels.dump_to_list(),
         })
    return respond(request, 'Edit', 'edit.html', render_dict)

  try:
    doc = library.fetch_doc(trunk_id, doc_id)
  except (models.InvalidTrunkError, models.InvalidDocumentError):
    return HttpResponse("No such document exists", status=404)

  doc_contents = library.get_doc_contents_simple(doc, users.get_current_user())

  tags = ','.join(doc.tags)
  render_dict.update(
      {'doc': doc,
       'doc_contents': doc_contents,
       'data_valid_range': constants.VALID_GRADE_RANGE,
       'doc_id': str(doc.key()),
       'trunk_id': str(doc.trunk_ref.key()),
       'tags': tags,
       'allowed_labels': models.AllowedLabels.dump_to_list(),
       })
  return respond(request, constants.DEFAULT_TITLE, "edit.html", render_dict)


def duplicate(request):
  """Duplicate the current document

  Args:
    trunk_id, doc_id: the current document
    parent_id, parent_trunk: the parent document

    Create a copy the current document, and place a link to it in the
    parent document, immediately after the DocLink that points at the
    current document.
  """
  trunk_id = request.GET.get('trunk_id')
  doc_id = request.GET.get('doc_id')

  doc = library.fetch_doc(trunk_id, doc_id)
  clone = doc.clone()
  clone.setClonedTitle()
  clone.placeInNewTrunk()
  goto_trunk = clone.trunk_ref.key()
  goto_id = clone.key()

  parent_trunk = request.GET.get('parent_trunk')
  parent_id = request.GET.get('parent_id')
  if parent_trunk and parent_id:
    parent = library.fetch_doc(parent_trunk, parent_id)
    newparent = parent.clone()
    newparent.insert_after(doc, clone)
    parent.updateTrunkHead(newparent)
    library.update_visit_stack(clone, newparent, users.get_current_user())

  # redirect to edit mode
  return HttpResponseRedirect(
      '/edit?%s' %
      urllib.urlencode([
          ('trunk_id', goto_trunk),
          ('doc_id', goto_id),
          ]))


def view_doc(request):
  """Displays document from provided trunk and doc ids.

  NOTE(mukundjha): If paramater 'absolute' is passed in the request, user
    is shown the document pointed to by the doc id (or latest if only trunk
    id is passed) and does not take into account user's view histroy. This
    is useful in many cases like migrating to latest version, saving an edit
    etc.
  TODO(mukundjha): Merge with /(root) and handle other types in template

  Args:
    trunk_id: Trunk Id for the required doc.
    doc_id: Doc Id associated with the doc. This just shows the entry point
      for the request and only plays a role if 'absolute' is set true.
    parent_trunk: Trunk Id of the parent. Required to build up correct hierarchy.
    parent_id: Doc Id for the parent. Again its just marks an entry point.
    absolute: If set, doc pointed by the doc_id is fetched, irrespective
      of user's history or latest version of the doc.
    use_history: If set user's history is used to fetch the doc. If use_history
      is set user will always land on the same version of the doc he was on last
      visit, until he chooses to move to a newer version.
    abs_path: Specifies path to be followed to reach the doc. This is useful in
      cases where links are bookmarks and a particular hierarchy is to be followed.
    came_from: When the user came to this document by following a 'next' link
      in a document at a deeper level, this specifies that document.  The next link
      on this document needs to take it into account when pointing at a document
      at a lower level.
  """
  trunk_id = request.GET.get('trunk_id')
  doc_id = request.GET.get('doc_id')
  parent_trunk = request.GET.get('parent_trunk')
  parent_id = request.GET.get('parent_id')
  use_absolute_addressing = request.GET.get('absolute')
  use_history = request.GET.get('use_history')
  came_from = request.GET.get('came_from')

  # This would be set true if path argument is present
  abs_path = request.GET.get('abs_path')

  if abs_path:
    use_absolute_mapping_for_path = True
  else:
    use_absolute_mapping_for_path = False

  prev_doc = library.get_doc_for_user(trunk_id, users.get_current_user())
  try:
    if use_absolute_addressing:
      doc = library.fetch_doc(trunk_id, doc_id)
    elif use_history:
      doc = prev_doc
    else:
      doc = library.fetch_doc(trunk_id)

  except (models.InvalidTrunkError, models.InvalidDocumentError):
    return HttpResponse("No such document exists", status=404)


  doc_contents = library.get_doc_contents(
      doc, users.get_current_user(), resolve_links=True,
      use_history=use_history, fetch_score=True, fetch_video_state=True)

  current_doc_score = doc.get_score(users.get_current_user())

  doc_score = current_doc_score

  # If progress is 100, we don't recompute the score for the page.
  # until user chooses to reset the score. Here we are just updating
  # the timestamp of the visit (and recording the visited version).
  # When it is not 100, it will be updated via AJAX.

  if current_doc_score == 100:
    library.put_doc_score(doc, users.get_current_user(), 100)
    doc_score = 100
  trunk = doc.trunk_ref

  if parent_trunk:
    parent = library.fetch_doc(parent_trunk, parent_id)
  else:
    parent = None


  updated_stack = library.update_visit_stack(doc, parent,
                                             users.get_current_user())
  # Page itself is a course
  # TODO(vchen): Update recent course should be a background task.
  if doc.label == models.AllowedLabels.COURSE:
    library.update_recent_course_entry(doc, doc,
                                       users.get_current_user())
  if updated_stack.path:
    traversed_path = library.expand_path(updated_stack.path, use_history,
                                         use_absolute_mapping_for_path,
                                         users.get_current_user())
    root_doc = traversed_path[0]
    if root_doc.label == models.AllowedLabels.COURSE:
      library.update_recent_course_entry(doc, root_doc,
                                         users.get_current_user())
  else:
    traversed_path = []

  if came_from:
    came_from = db.get(came_from)
  (prev_url, next_url) = library.getPrevNextLinks(doc, updated_stack, came_from)
  if prev_url:
    prev_url = '/view?' + urllib.urlencode(prev_url)
  if next_url:
    next_url = '/view?' + urllib.urlencode(next_url)

  if not use_history:
    link_to_prev = (
        '<a href='
        '"/view?trunk_id=%s&doc_id=%s&absolute=True&use_history=True">'
        'Show as it was last time</a>' % (trunk.key(), prev_doc.key())
        )
  else:
    link_to_prev =  (
        '<a href="/view?trunk_id=%s">Show latest</a>' % trunk.key())

  dup_params = [
      ('trunk_id', trunk.key()),
      ('doc_id', doc.key()),
      ]
  if parent:
    dup_params.extend([
        ('parent_trunk', parent.trunk_ref.key()),
        ('parent_id', parent.key())
        ])

  menu_items = [
    '<a href="/edit">Create New</a>',
    '<a href="/edit?trunk_id=%s&doc_id=%s">Edit this page</a>' %
    (trunk.key(), doc.key()),
    '<a href="/duplicate?%s">Duplicate</a>' % urllib.urlencode(dup_params),
    link_to_prev,
    '<a href="/history?trunk_id=%s">History</a>' % (trunk.key()),
    ]

  main_menu = ' | '.join(menu_items)

  title_items = [
    constants.DEFAULT_TITLE,
    '<div id="docProgressContainer">',
    '<b>Progress: %s</b></div>' % (doc_score)
    ]
  title = ''.join(title_items)

  annotation = library.get_doc_annotation(
      doc, users.get_current_user(), doc_contents=doc_contents)
  return respond(request, title, "view.html",
                {'doc': doc,
                'doc_score': doc_score,
                'doc_contents': doc_contents,
                'traversed_path': traversed_path,
                'annotation': annotation,
                'next': next_url,
                'prev': prev_url,
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
  preKey = request.GET.get('pre')
  postKey = request.GET.get('post')
  pre = db.get(preKey)
  post = db.get(postKey)
  text = library.show_changes(pre, post)
  prevpair = None
  nextpair = None

  trunk = db.get(trunk_id)
  revs = [i.obj_ref
          for i in models.TrunkRevisionModel.all().ancestor(trunk).order(
              '-created')]
  for it, previous in itertools.izip(revs, revs[1:] + [None]):
    if previous is None:
      continue
    if previous == postKey:
      nextpair = (it, previous)
    elif it == preKey:
      prevpair = (it, previous)

  return respond(
      request, constants.DEFAULT_TITLE, "changes.html",
      {
          'trunk_id': trunk_id,
          'text': text,
          'prevpair': prevpair,
          'nextpair': nextpair,
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
    return HttpResponseRedirect(
        '/view?trunk_id=%s&doc_id=%s&absolute=True' % (trunk_id, doc_id))


def get_session_id_for_widget(request):
  """Returns session id tied with user and widget.

  NOTE: BadKeyError was not checked on purpose, so that exception is raised.
  """
  widget_id = request.GET.get('widget_id')
  widget = db.get(widget_id)

  session_id = library.get_or_create_session_id(widget,
                                                users.get_current_user())
  if session_id:
    return HttpResponse(simplejson.dumps({'session_id' : session_id}))


def get_doc_score(request):
  """Gets the document score via asynchronously.

  It also computes accumulated score for the document and sends it back.

  TODO(mukundjha): Slightly inefficient with many calls to datastore,
    should use mem-cache.

  Query Parameters:
    trunk_id: Trunk id of the document
    doc_id: Key of the document.

  Respose:
    JSON encoded:
    { 'doc_score': score }
  """
  trunk_id = request.GET.get('trunk_id')
  doc_id = request.GET.get('doc_id')
  user = users.get_current_user()

  # Using absolute addressing
  doc = library.fetch_doc(trunk_id, doc_id)
  doc_score = doc.get_score(user)
  if doc_score < 100:
    doc_contents = library.get_doc_contents_simple(doc, user)
    doc_score = library.get_accumulated_score(doc, user, doc_contents,
                                              recurse=False)
  return HttpResponse(simplejson.dumps({ 'doc_score': doc_score }))


def update_doc_score(request):
  """Updates score for the widget and the doc and returns updated doc score.

  Function revceives updated status (both score and progres) from widget and
  updates score record for associated user and widget. It also recomputes
  accumulated score for the document from which updates are recieved and
  sends back updated score for the document.

  NOTE(mukundjha): Doc id passed to the widget is of the same doc that is
  presented to the user, so we can use absolute binding to update the score.
  If we fetch the appropriate document everytime we update score, there might
  be a case when document gets updated while user is working on it and the
  function ends up fetching and updating score according to new document.

  TODO(mukundjha): Check for possible race conditions on score updates.
  TODO(mukundjha): Slightly inefficient with many calls to datastore,
    should use mem-cache.

  Parameters:
    widget_id: Key for the widget.
    progress: integer between 0-100 indicating progress of the widget.
    score: integer between 0-100 indicating score for the widget.
    trunk_id: Key for the trunk associated with doc containing the widget.
    doc_id: Key of the document.
    parent_trunk: Key for the trunk associated with parent.
    parent_doc: Key for the parent doc.
  """
  widget_id = request.GET.get('widget_id')
  progress = int(request.GET.get('progress'))
  score = int(request.GET.get('score'))
  trunk_id = request.GET.get('trunk_id')
  doc_id = request.GET.get('doc_id')
  parent_trunk =  request.GET.get('parent_trunk')
  parent_doc = request.GET.get('parent_doc')

  widget = db.get(widget_id)
  library.put_widget_score(widget, users.get_current_user(), progress)

  # Using absolute addressing
  doc = library.fetch_doc(trunk_id, doc_id)
  doc_contents = library.get_doc_contents_simple(doc, users.get_current_user())

  # No recursive
  doc_score = library.get_accumulated_score(doc, users.get_current_user(),
                                            doc_contents)
  library.set_dirty_bits_for_doc(doc, users.get_current_user())

  return HttpResponse(simplejson.dumps({'doc_score' : doc_score}))


def update_trunk_title(request):
  query = models.TrunkModel.all()
  for trunk in query:
    try:
      head = db.get(trunk.head)
      if not head or not isinstance(head, models.DocModel):
        continue
      trunk.title = head.title
      trunk.put()
    except BadKeyError:
      pass
  return get_list_ajax(request)


def get_list_ajax(request):
  """Sends a list of documents present in data store.

  Useful in populating list for Link Picker while editing the document.

  Args:
    q: limit the response with prefix match on titles
    s: return the list starting at this index (i.e. skip this many)
    c: return only this many entries
  """
  query = models.TrunkModel.all()
  search = request.REQUEST.get('q', '')

  def asInt(request, field, defval):
    try:
      sval = request.REQUEST.get(field, defval)
      val = int(sval)
    except ValueError:
      val = defval
    return val

  startAt = asInt(request, 's', 0)
  count = asInt(request, 'c', 8)

  if search != '':
    query = query.filter("title >=", search)
    query = query.filter("title <", search + u"\ufffd")
  query.order("title")

  doc_list = []
  atEnd = 0
  for trunk in query:
    try:
      head = db.get(trunk.head)
      if not head or not isinstance(head, models.DocModel):
        continue
      doc_list.append({
          'doc_title': head.title,
          'trunk_id': str(trunk.key()),
          'doc_id': str(head.key()),
          })
      # Self-correction.  For some unknown reason (NEEDSWORK),
      # the index will go out of sync immediately after editing
      # a document.
      if True and (head.title != trunk.title):
        trunk.title = head.title
        trunk.put()
    except db.BadKeyError:
      pass
    if startAt + count < len(doc_list):
      break
  else:
    atEnd = 1

  if startAt:
    doc_list = doc_list[startAt:]
  if count:
    doc_list = doc_list[0:count]

  return HttpResponse(simplejson.dumps({
      'doc_list': doc_list,
      'startAt': startAt,
      'count': len(doc_list),
      'atEnd': atEnd,
      }))


def new_document_ajax(request):
  """Create a new stub document and returns its id"""
  one = models.DocModel.insert_with_new_key()
  one.title = request.REQUEST.get('title', "(New Page)")
  blurb = models.RichTextModel.insert_with_new_key()
  blurb.data = ""
  blurb.put()
  one.content.append(blurb.key())
  one.placeInNewTrunk()
  result = {
      'doc_title': one.title,
      'trunk_id': str(one.trunk_ref.key()),
      'doc_id': str(one.key()),
      };
  return HttpResponse(simplejson.dumps(result))


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


def fetch_from_tags(request):
  """Fetches courses with given tag.

  TODO(mukundjha): Pick unique courses.
  """
  tag = request.GET.get('tag')
  course_list = []
  courses = models.DocModel.all().filter('tags =', tag).filter(
      'label =', models.AllowedLabels.COURSE).order('-created').fetch(20)
  seen = {}
  for doc in courses:
    t = doc.trunk_ref
    k = t.key()
    if k not in seen:
      seen[k] = t.head
      d = db.get(t.head)
      course_list.append(d)

  return respond(request, constants.DEFAULT_TITLE, "course_list.html",
                 {'course_list' : course_list, 'tag': tag})


def subjectsDemo(request):
  """/subjectsDemo - Test of the subjects menu."""

  return respond(request, 'SUBJECTS', 'subjects.html', {});


# Regex to extract the subject ID.  group(1) should be empty or have the
# subject ID.
_SUBJECT_RE = re.compile(r'/subjects/(.*)')


def subjectsJson(request):
  """/subjects/.* - RESTful API for returning subject taxonomy

  By default, returns 2-level hierarchy.

  /subjects/ returns root menu.
  /subjects/<id> returns children of <id>
  """
  match = _SUBJECT_RE.match(request.path)
  if match:
    subject_id = match.group(1)
    taxonomy = subjects.GetSubjectsTaxonomy()
    if subject_id:
      subject_id = urllib.unquote_plus(subject_id)
      response = subjects.GetSubjectsJson(taxonomy, subject_id)
    else:
      response = subjects.GetSubjectsJson(taxonomy, None)
    return HttpResponse(response)
  return HttpResponse("Invalid subject request: " + request.path,
                      status=404)


def mark_as_read(request):
  """Marks a page as read and updates score entries."""
  trunk_id = request.GET.get('trunk_id')
  doc_id = request.GET.get('doc_id')
  doc = library.fetch_doc(trunk_id, doc_id)

  library.put_doc_score(doc, users.get_current_user(), 100)
  library.set_dirty_bits_for_doc(doc, users.get_current_user())
  return HttpResponse("True")


def store_video_state(request):
  """Stores the state when a video is paused."""
  video_id = request.GET.get('video_id')
  current_time = request.GET.get('current_time', 0.0)

  video = db.get(video_id)
  video_state = models.VideoState.all().filter(
      'video_ref =', video).filter('user =', users.get_current_user()).get()

  if video_state:
    video_state.paused_time = float(current_time)
    video_state.put()
  else:
    library.insert_with_new_key(
        models.VideoState, video_ref=video, user=users.get_current_user(),
        paused_time=float(current_time))
  return HttpResponse('True')


def reset_score_for_page(request):
  """Resets score for a page and updates score entries."""
  trunk_id = request.GET.get('trunk_id')
  doc_id = request.GET.get('doc_id')
  doc = library.fetch_doc(trunk_id, doc_id)

  library.put_doc_score(doc, users.get_current_user(), 0)
  library.set_dirty_bits_for_doc(doc, users.get_current_user())
  return HttpResponse("True")


@login_required
@post_required
@xsrf_required
def update_notes(request):
  """Update annotation on a given object

  This is called when the goog.ui.Popup that displayed the annotation
  to be edited is dismissed, with the result of editing.  The POST data
  consists of 'data' which is a JSON serialization of 'text' (annotation)
  and 'ball' (color in which the annotation indicator ball should be
  painted).
  """
  try:
    data = request.POST.get('data')
    it = simplejson.loads(data)
    trunk_id = it.get('trunk_id')
    doc_id = it.get('doc_id')
    content_id = it.get('name')
    content_id = re.sub(r'^[^-]+-', '', content_id)
    library.update_doc_content_annotation(trunk_id, doc_id, content_id,
                                          users.get_current_user(), data)
  except Exception, e:
    content_id = str(e)
    data = request.POST.get('data')

  return respond(request, "Received", "debugnotes.html",
                 { 'data': data, 'name': content_id })


@login_required
@post_required
@xsrf_required
def get_notes(request):
  """Get annotation on a given object

  This is called when the goog.ui.Popup that will display the annotation
  to be edited is about to be opened.  The POST data consists of 'data'
  which is a JSON serialization of 'name' ("note-" + id) where id identifies
  which AnnotationState object the request is about.
  """
  ball = text = ''
  try:
    data = request.POST.get('data')
    it = simplejson.loads(data)
    trunk_id = it.get('trunk_id')
    doc_id = it.get('doc_id')
    content_id = it.get('name')

    # Strip leading 'note##-' from the name to extract the content_id.
    content_id = re.sub(r'^[^-]+-', '', content_id)

    # Prepare default response.
    d = {'text': '', 'ball': 'plain'}
    try:
      data = library.get_annotation_data(trunk_id, doc_id, content_id,
                                         users.get_current_user())
      if data:
        d = simplejson.loads(data)
    except ValueError, e:
      #logging.warn("--------- get_notes: error = %r" % e)
      pass

    text = d.get('text', '')
    ball = d.get('ball', 'plain')

  except Exception, e:
    content_id = str(e)
    text = request.POST.get('data')

  return HttpResponse(simplejson.dumps({
      'text': text,
      'ball': ball,
      'name': content_id,
      }))


@login_required
@post_required
@xsrf_required
def get_notepad(request):
  """Get notepad contents

  Parameters:
    key: NotePad object's key
  Returns:
    text: NotePad data
    key: given key (primarily for debugging)
  """
  try:
    key = request.REQUEST.get('key')
    text = library.get_notepad(str(key), users.get_current_user())

  except Exception, e:
    key = str(e)
    text = request.REQUEST.get('key')

  return HttpResponse(simplejson.dumps({
      'text': text,
      'key': key,
      }))


@login_required
@post_required
@xsrf_required
def update_notepad(request):
  """Update notepad contents

  Args:
    key: NotePad object's key
    text: NotePad data
  """
  try:
    key = request.POST.get('key')
    text = request.POST.get('text')
    library.update_notepad(str(key), users.get_current_user(), text)
  except Exception, e:
    text = key
    key = str(e)

  return HttpResponse(simplejson.dumps({
      'text': text,
      'key': key,
      }));
