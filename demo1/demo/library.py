# Copyright 2008 Google Inc.
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

# Copied substantially from rietveld:
#
#  http://code.google.com/p/rietveld
#
# Removed all rietveld-specific codereview templates.
# TODO(vchen): Determine what other functionality to retain.

"""Django template library for Lantern."""

import cgi
import logging
import traceback
import os
import base64
import string
import random
import re

from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import db

import django.template
import django.utils.safestring
from django.core.urlresolvers import reverse

import models
import yaml
import constants

# For registering filter and tag libs.
register = django.template.Library()


@register.filter
def subtract_one(arg):
  """Subtracts one from the provided number."""
  num = int(arg)
  return num-1


@register.filter
def get_element(list, pos):
  """Subtracts one from the provided number."""
  return list[pos]


@register.filter
def get_range(upper):
  """Returns a list with integer between the range provided.
  
  Args:
  """
  return range(upper)


@register.filter
def class_name(cls):
  """Returns name of the class."""
  return cls.__class__.__name__


@register.filter
def get_key(cls):
  """Returns key for an object if it exists in datastore."""
  try:
    object_key = cls.key()
  except db.NotSavedError:
    return None
  return str(object_key)


@register.filter
def show_user(email, arg=None, autoescape=None, memcache_results=None):
  """Render a link to the user's dashboard, with text being the nickname."""
  if isinstance(email, users.User):
    email = email.email()
  if not arg:
    user = users.get_current_user()
    if user is not None and email == user.email():
      return 'me'

  if memcache_results is not None:
    ret = memcache_results.get(email)
  else:
    ret = memcache.get('show_user:' + email)

  if ret is None:
    logging.debug('memcache miss for %r', email)
    account = models.Account.get_account_for_email(email)
    if account is not None and account.user_has_selected_nickname:
      ret = ('<a href="%s" onMouseOver="M_showUserInfoPopup(this)">%s</a>' %
             (reverse('demo.views.show_user', args=[account.nickname]),
              cgi.escape(account.nickname)))
    else:
      # No account.  Let's not create a hyperlink.
      nick = email
      if '@' in nick:
        nick = nick.split('@', 1)[0]
      ret = cgi.escape(nick)

    memcache.add('show_user:%s' % email, ret, 300)

    # populate the dict with the results, so same user in the list later
    # will have a memcache "hit" on "read".
    if memcache_results is not None:
      memcache_results[email] = ret

  return django.utils.safestring.mark_safe(ret)


@register.filter
def show_users(email_list, arg=None):
  """Render list of links to each user's dashboard."""
  if not email_list:
    # Don't wast time calling memcache with an empty list.
    return ''
  memcache_results = memcache.get_multi(email_list, key_prefix='show_user:')
  return django.utils.safestring.mark_safe(', '.join(
      show_user(email, arg, memcache_results=memcache_results)
      for email in email_list))


def get_nickname(email, never_me=False, request=None):
  """Return a nickname for an email address.

  If 'never_me' is True, 'me' is not returned if 'email' belongs to the
  current logged in user. If 'request' is a HttpRequest, it is used to
  cache the nickname returned by models.Account.get_nickname_for_email().
  """
  if isinstance(email, users.User):
    email = email.email()
  if not never_me:
    if request is not None:
      user = request.user
    else:
      user = users.get_current_user()
    if user is not None and email == user.email():
      return 'me'

  if request is None:
    return models.Account.get_nickname_for_email(email)
  else:
    if getattr(request, '_nicknames', None) is None:
      request._nicknames = {}
    if email in request._nicknames:
      return request._nicknames[email]
    result = models.Account.get_nickname_for_email(email)
    request._nicknames[email] = result
  return result


class NicknameNode(django.template.Node):
  """Renders a nickname for a given email address.

  The return value is cached if a HttpRequest is available in a
  'request' template variable.

  The template tag accepts one or two arguments. The first argument is
  the template variable for the email address. If the optional second
  argument evaluates to True, 'me' as nickname is never rendered.

  Example usage:
    {% cached_nickname msg.sender %}
    {% cached_nickname msg.sender True %}
  """

  def __init__(self, email_address, never_me=''):
    """Constructor.

    'email_address' is the name of the template variable that holds an
    email address. If 'never_me' evaluates to True, 'me' won't be returned.
    """
    self.email_address = django.template.Variable(email_address)
    self.never_me = bool(never_me.strip())
    self.is_multi = False

  def render(self, context):
    try:
      email = self.email_address.resolve(context)
    except django.template.VariableDoesNotExist:
      return ''
    request = context.get('request')
    if self.is_multi:
      return ', '.join(get_nickname(e, self.never_me, request) for e in email)
    return get_nickname(email, self.never_me, request)


@register.tag
def nickname(parser, token):
  """Almost the same as nickname filter but the result is cached."""
  try:
    tag_name, email_address, never_me = token.split_contents()
  except ValueError:
    try:
      tag_name, email_address = token.split_contents()
      never_me = ''
    except ValueError:
      raise django.template.TemplateSyntaxError(
        "%r requires exactly one or two arguments" % token.contents.split()[0])
  return NicknameNode(email_address, never_me)


@register.tag
def nicknames(parser, token):
  """Wrapper for nickname tag with is_multi flag enabled."""
  node = nickname(parser, token)
  node.is_multi = True
  return node

### functions to parse yaml files ###


def parse_yaml(path):
  """Parses input yaml file and returns a dictionary object with yaml content.

  Validation of the content is done by parse_leaf and parse_node functions.

  Args:
    path: Path to yaml file.

  Returns:
    A dict object with yaml_content mapped with corresponding keys.

  Raises:
    IOError:  If file path is not correct.
    YAMLError: If unable to load yaml file.

  If an error occours the dictionary object returned will contain
  element 'errorMsg' containing the error message.
  """
  # Read the yaml file.
  try:
    data_file_content = open(path).read()

  # If file not valid return dictObejct with corresponding error message.
  except IOError:
    return {'errorMsg':'ERROR: File path not correct ' + path}

  try:
    data_dict = yaml.load(data_file_content)
  # If file unable to load yaml content return dictObejct with corresponding error message.
  except yaml.YAMLError, exc:
    return {'errorMsg':'Error: Unable to load yaml content from %s<br> ' +
      'Details:<br>\n%s'% (path, str(exc))}

  if not isinstance(data_dict, dict):
    return {'errorMsg':'ERROR: (DICTIONARY OBJECT EXPECTED) Error loading yaml' +
      'content from ' + path }

  return data_dict


def parse_node(path):
  """Parses a yaml file and validates if the file is of type node.

  Args:
    path: Path to yaml file.

  Returns:
    A dict object with doc_contents mapped with corresponding keys,
      or with appropriate error message.
  """
  data_dict = parse_yaml(path)

  if 'errorMsg' in data_dict:
    return data_dict

  if data_dict.get(constants.YAML_TYPE_KEY) != "group":
    return {'errorMsg':'Error loading yaml file ( '+path+' ):  invalid leaf'}

  return data_dict


def parse_leaf(path):
  """Parses a yaml file and validates if the file is of type leaf.

  Args:
    path: Path to yaml file.

  Returns:
    A dict object with yaml_content mapped with corresponding keys,
      or with appropriate error message, if there is a type mismatch.
  """
  data_dict = parse_yaml(path)

  if 'errorMsg' in data_dict:
    return data_dict

  if data_dict.get(constants.YAML_TYPE_KEY) != "content":
    return {'errorMsg':'Error loading yaml file ( '+path+' ):  invalid leaf'}

  return data_dict

### Library function to interact with datastore ###

def gen_random_string(num_chars=16):
  """Generates a random string of the specified number of characters.

  First char is chosen from set of alphabets as app engine requires
  key name to start with an alphabet. Also '-_' are used instead of
  '+/' for 64 bit encoding.

  Args:
    num_chars: Length of random string.
  Returns:
    Random string of length = num_chars
  """
  # Uses base64 encoding, which has roughly 4/3 size of underlying data.
  first_letter = random.choice(string.letters)
  num_chars -= 1
  num_bytes = ((num_chars + 3) / 4) * 3
  random_byte = os.urandom(num_bytes)
  random_str = base64.b64encode(random_byte, altchars='-_')
  return first_letter+random_str[:num_chars]


def insert_with_new_key(cls, parent=None, **kwargs):
  """Insert model into datastore with a random key.

  Args:
    cls: Data model class (ex. models.DocModel).
    parent: optional parent argument to bind models in same entity group.
      NOTE: If parent argument is passed, key_name may not be unique across
      all entities.
  Returns:
    Data model entity or None if error.

  TODO(mukundjha): Check for race condition.
  """
  while True:
    key_name = gen_random_string()
    entity = cls.get_by_key_name(key_name, parent=parent)
    if entity is None:
      entity = cls(key_name=key_name, parent=parent, **kwargs)
      entity.put()
      break
    else:
      logging.info("Entity with key "+key_name+" exists")

  return entity


def create_new_trunk_with_doc(doc_id, **kwargs):
  """Creates a new trunk with given document as head.

  WARNING: Since we are passing parent parameter in insert_with_new_key,
  function will only check for uniqueness of key among entities having 'trunk'
  as an ancestor. This no longer guarantees unique key_name across all entities.

  NOTE(mukundjha): No check is done on doc_id, it's responsibility of
  other functions calling create_new_trunk_with_doc to check the parameter
  before its passed.

  Args:
    doc_id: String value of key of the document to be added.
  Returns:
    Returns created trunk.
  Raises:
    InvalidDocumentError: If the doc_id is invalid.
  """
  trunk = insert_with_new_key(models.TrunkModel)

  message = kwargs.pop('commit_message', 'Commited a new revision')
  trunk_revision = insert_with_new_key(models.TrunkRevisionModel, parent=trunk,
    obj_ref=doc_id, commit_message=message)

  trunk.head = doc_id
  trunk.put()
  return trunk


def append_to_trunk(trunk_id, doc_id, **kwargs):
  """Appends a document to end of the trunk.

  NOTE(mukundjha): No check is done on doc_id, it's responsibility of
  other functions calling append_to_trunk to check the parameter
  before its passed.

  Args:
    trunk_id: Key of the trunk.
    doc_id: String value of key of the document to be added.
  Returns:
    Returns modified trunk.
  Raises:
    InvalidDocumentError: If the doc_id is invalid.
    InvalidTrunkError: If the trunk_id is invalid.
  """
  try:
    trunk = db.get(trunk_id)
  except db.BadKeyError, e:
    raise models.InvalidTrunkError('Trunk is not valid %s',
      trunk_id)

  message = kwargs.pop('commit_message', 'Commited a new revision')
  trunk_revision = insert_with_new_key(models.TrunkRevisionModel, parent=trunk,
    obj_ref=doc_id, commit_message=message)

  trunk.head = doc_id
  trunk.put()
  return trunk


def create_new_doc(trunk_id=None, **kwargs):
  """Creates a new document in datastore.

  If trunk_id is provided, new document is appended to the trunk.
  Else a new trunk is created.

  Args:
    trunk_id: key(string) to the trunk to which the new document belongs.
  Returns:
    A DocModel object.
  Raises:
    InvalidTrunkError: If an invalid trunk id is provided
    InvalidDocumentError: If unable to save document in data store

  TODO(mukundjha): Check all db.put statements for exceptions.
  """

  if trunk_id:
    try:
      trunk = db.get(trunk_id)
    except db.BadKeyError, e:
      raise models.InvalidTrunkError('Invalid Trunk id %s', str(trunk_id))

    doc = insert_with_new_key(models.DocModel)
    doc_key = str(doc.key())
    trunk = db.run_in_transaction(append_to_trunk, trunk.key(), doc_key,
      **kwargs)
  else:

    doc = insert_with_new_key(models.DocModel)
    doc_key = str(doc.key())
    trunk = db.run_in_transaction(create_new_trunk_with_doc, doc_key,
     **kwargs)

  if not trunk:
    doc.delete()
    raise models.InvalidDocumentError('Unable to create/append to trunk')

  doc.trunk_ref = trunk.key()
  doc.put()

  return doc


def fetch_doc(trunk_id, doc_id=None):
  """Fetches a document from datastore or raises InvalidDocumentError.

  If both trunk_id and doc_id are provided, return particular doc if it belongs
  to the given trunk, else return head of the trunk.

  Args:
    trunk_id: Trunk to fetch the document from.
    doc_id: Document id to fetch a particular version of document.
  Returns:
    A DocModel object which having provided trunk_id and doc_id, if only
      trunk_id is provided or an invalid doc_id is provided head of the
      trunk is returned.
  Raises:
    InvalidDocumentError: If trunk_id passed is invalid.
  """
  try:
    trunk = db.get(trunk_id)
  except db.BadKeyError, e:
    raise models.InvalidTrunkError('Invalid trunk id: %s', trunk_id)

  if doc_id:
    try:
      doc = db.get(doc_id)
    except db.BadKeyError, e:
      raise models.InvalidDocumentError('No document Found with provided key')

    trunk_revisions = models.TrunkRevisionModel.all().ancestor(trunk)
    trunk_revision_with_doc = trunk_revisions.filter('obj_ref =',
                                                      str(doc.key()))

    if trunk_revision_with_doc.count():
      return doc
    else:
      raise models.InvalidDocumentError("No document Found")

  # Using cached value of head stored in trunk, should be fine since all
  # writes are atomic and updates head.

  if trunk.head:
    return db.get(trunk.head)
  else:
    raise models.InvalidDocumentError("Trunk has no head document!")


def get_doc_for_user(trunk_id, user):
  """Retrieves document based on user's visit history.

  If the user has visited a particular revision (document of a trunk),
  user will see that document, else user will be directed to the
  latest revision.

  We pass user instead of using users.get_current_user, so that this function
  could also be used while creating other pages like teacher's dashboard etc.,
  where student will not be looged in.

  NOTE(mukundjha): This does not update the datastore with new entry.
    It is upto the view to update the datastore.

  Args:
    trunk_id: Key to the referenced trunk.
    user: User whose history is to be used.
  Returns:
    Document based on user's visit history.
  Raises:
    InvalidTrunkError: If trunk_id is not valid.
  """
  try:
    trunk = db.get(trunk_id)
  except db.BadKeyError, e:
    raise models.InvalidTrunkError('Invalid trunk %s', trunk_id)

  query = models.DocVisitState.all().filter('user =', user).filter(
      'trunk_ref =', trunk).order('-last_visit')

  if query.count():
    doc_entry = query.get()
    return doc_entry.doc_ref
  else:
    doc = db.get(trunk.head)
    return doc


def get_parent(doc):
  """Returns a parent for a document.

  If multiple parents are present, choose one based on ranking function.
  Note(mukundjha): Taking history into account makes it a very heavy on
  datastore.

  Args:
    doc: DocModel object from datastore.
  Returns:
    Document which is parent of doc passed or None if there are no
    parents.
  """
  parent_entry = models.DocLinkModel.all().filter('doc_ref =', doc).order(
       '-created').get()

  if parent_entry:
    return parent_entry.from_doc_ref
  else:
    return None


def get_score_for_link(link_element, user, **kwargs ):
  """Calculates score for the DocLink object.
  
  Score for a link is essentially score for the trunk pointed by the link.
  If dirty bit is set for the visit entry for the referred trunk scores 
  for the doc are re-computed by calling get_accumulated_score, else
  score entry for the trunk is fetched.
  
  NOTE(mukundjha): Does not take care of cycles.

  Args:
    link_element: Link object for which score is required.
    user: User whose score is desired.

    These arguments are passed as **kwargs.

    use_history: If set user's history is used to fetch the doc.
    recurse: If set True, all the scores will be recursively computed
      and updated.

  Returns: 
    Score for the link object.
  """
  use_history = kwargs.pop('use_history', False)
  recurse = kwargs.pop('recurse', False)

  if recurse:
    if use_history:
      doc = get_doc_for_user(link_element.trunk_ref.key(), user)
    else:
      doc = fetch_doc(link_element.trunk_ref.key())
    doc_contents = get_doc_contents(doc, user, resolve_links=True,
                                    use_history=use_history)

    return get_accumulated_score(doc, user, doc_contents,
                                 use_history=use_history,
                                 recurse=recurse)
  else:
    visit_state = models.DocVisitState.all().filter('user =', user).filter(
        'trunk_ref =', link_element.trunk_ref).get()

    if visit_state and visit_state.dirty_bit:
      if use_history:
        new_doc = get_doc_for_user(link_element.trunk_ref.key(), user)
      else:
        new_doc = fetch_doc(link_element.trunk_ref.key())
        doc_contents = get_doc_contents(new_doc, user, resolve_links=True,
                                      use_history=use_history)

        score = get_accumulated_score(new_doc, user, doc_contents,
                                     use_history=use_history,
                                     recurse=recurse)
        return score

    elif visit_state:
      return visit_state.progress_score
    else:
      return 0


def get_accumulated_score(doc, user, doc_contents, **kwargs):
  """Calculate score for a doc by accumulating scores from its objects.
  
  Averages score, no weights. It also updates the score for element.

  Args:
    doc: Document fetching the score.
    doc_contents: List of objects referenced in list of contents of the doc.
      the list is passed separately to prevent repeated calls to data-store
      for objects.
    user: User associated with the score.
    
    These arguments are passed in **kwargs.
    
    use_history: If set user's history is used to fetch the document.
    recurse: If set True scores are recursively re-computed instead of just
      picking entries from datastore.
  Returns:
    Average score based on content of the document. Also adds score attribute
    to each 'scorable' element.
  """
  use_history = kwargs.pop('use_history', False)
  recurse = kwargs.pop('recurse', False)
   
  total, count = 0, 0
  for element in doc_contents:
    if not isinstance(element, models.DocLinkModel): 
      element.score = element.get_score(user)
    else:
      element.score = get_score_for_link(element, user,
                                         use_history=use_history,
                                         recurse=recurse)

    if element.score is not None:
      total += element.score
      count += 1

  if total and count:
    total = int(round(float(total)/count))
    put_doc_score(doc, user, total)
    return total
  else:
    put_doc_score(doc, user, 0)
    return 0


def put_doc_score(doc, user, score):
  """Stores progress score for a doc.

  Updates the entry with new score if present, else makes a new entry.
  We could also just append if we want to track the progress over time.

  Args:
    doc: Document fetching the score.
    user: User associated with the score.
    score: Current score.
  TODO(mukundjha): Determine if this needs to be run in a transaction.
  """
  visit_state = models.DocVisitState.all().filter('user =', user).filter(
    'trunk_ref =', doc.trunk_ref).get()

  if visit_state:
    visit_state.progress_score = score
    visit_state.doc_ref = doc
    visit_state.dirty_bit = False
    visit_state.put()
  else:
    visit_state = insert_with_new_key(models.DocVisitState, user=user,
                                      trunk_ref=doc.trunk_ref.key(),
                                      doc_ref=doc.key(), progress_score= score)


def get_doc_contents(doc, user, **kwargs):
  """Return a list of objects referred by keys in content list of a doc.

  NOTE(mukundjha): doc is a DocModel object and not an id.
  Args:
    doc: DocModel used for populating content objects.
    user: User in consideration.
    
    Arguments below are passed using **kwargs. By default all are set to
    false.

    resolve_links: If reslove_links is true, then links are resolved to
      get appropriate title for links.
    use_history: Use history to resolve links.
    fetch_score: If set true score is also appended to all objects.
    fetch_video_state: If set VideoModel object is appended with video's 
      state (stored paused time).
  
  Returns:
    An ordered list of objects referenced in content list of passed doc.
  Raises:
    BadKeyError: If element referred is invalid.
  
  TODO(mukundjha): Develop Better method to extract base url.
  """
  resolve_links = kwargs.pop('resolve_links', False) 
  use_history = kwargs.pop('use_history', False) 
  fetch_score = kwargs.pop('fetch_score', False) 
  fetch_video_state = kwargs.pop('fetch_video_state', False) 
   
  if not isinstance(doc, models.DocModel):
    return None
  else:
    content_list = []
    # Using regex to extract baseurl.
    # First replace '//' with __TEMP__ and then split on '/'
    # example http://localhost:8080/exercise/
    # baseurl = http://localhost:8080
    # This however does not work if we have '/quiz?'
    
    double_slash = re.compile('//') # For double slashes
    slash = re.compile('/') # Single slash
    temp = re.compile('__TEMP__')  # Temp symbol to replace // with
    re_question_mark = re.compile('\?') # For cases like '/quiz?' we split at '?'
    is_relative_link = re.compile('^/') # Starts with /

    for el in doc.content:
      element = db.get(el)
      if not isinstance(element, models.DocLinkModel):
        if fetch_score:
          element.score = element.get_score(user)

        # If widget : extract the base url, base url are passed to channel
        # to locate blank.html and relay.html pages.

        if isinstance(element, models.WidgetModel):
          if is_relative_link.match(element.widget_url): 
            temp_array = re_question_mark.split(element.widget_url)
            element.base_url = temp_array[0] + '/'
          else: 
            temp_array = slash.split(double_slash.sub('__TEMP__',
                                   element.widget_url))
            base_url = temp.sub('//', temp_array[0])
            element.base_url = base_url + '/'
        
        # If video object and fetch_video_status is true, status is fetched.
        elif isinstance(element, models.VideoModel):
          video_state = models.VideoState.all().filter(
              'video_ref =', element).filter(
              'user =', users.get_current_user()).get()
          if video_state:
            element.current_time = video_state.paused_time
        content_list.append(element)
      else:
        link = element
        if resolve_links and use_history:
          doc = get_doc_for_user(link.trunk_ref.key(), user)
          link.default_title = doc.title
        elif resolve_links:
          doc = fetch_doc(link.trunk_ref.key())
          link.default_title = doc.title

        if fetch_score:
          link.score = doc.get_score(user)
 
        content_list.append(link)
    return content_list


def put_widget_score(widget, user, score):
  """Stores progress score for a widget.

  Updates the entry with new score if present, else makes a new entry.

  Args:
    widget: WidgetModel object for which score is being updated.
    user: User associated with the score.
    score: Current score.
  TODO(mukundjha): Determine if this needs to be run in a transaction.
  """
  visit_state = models.WidgetProgressState.all().filter('user =', user).filter(
    'widget_ref =', widget).get()

  if visit_state:
    visit_state.progress_score = score
    visit_state.put()
  else:
    visit_state = insert_with_new_key(models.WidgetProgressState, user=user,
                                      widget_ref=widget, progress_score=score)


def get_path_till_course(doc, path=None, path_trunk_set=None):
  """Gets a list of parents with root as a course.
  
  Useful in cases where a user lands on a random page and page
  needs to be linked to a course.
  Currently just picking the most latest parent recursively up
  until a course is reached or there are no more parents to pick.

  NOTE(mukundjha): This function is very heavy on datastore.
  * Checking for first 1000 entries for an existing course 
  is slightly better than checking all entries.

  Args:
    doc: DocModel object in consideration.
    path: starting path

  Returns:
    A list of parents doc_ids with root as a course.
  """
  logging.info('****Path RCVD %r', path) 
  trunk_set = set()
  if path is None:
    path = []
  if path_trunk_set is None:
    path_trunk_set = set([doc.trunk_ref.key()])

  parent_entry = models.DocLinkModel.all().filter(
      'trunk_ref =', doc.trunk_ref).order(
      '-created').fetch(1000)

  # Flag is set if an alternate path is picked.
  alternate_picked_flag = 0
  alternate_parent = None

  for parent in parent_entry:
    if parent.from_trunk_ref.key() not in trunk_set:
      trunk_set.add(parent.from_trunk_ref.key())
      if parent.from_trunk_ref.key() not in path_trunk_set:
        if not alternate_picked_flag:
          alternate_parent = parent
          alternate_picked_flag = 1

        if parent.from_doc_ref.label == models.AllowedLabels.COURSE:
          path_trunk_set.add(parent.from_trunk_ref.key())
          path.append(parent.from_doc_ref)
          path.reverse()
          path_to_return = [el.key() for el in path]
          return path_to_return
     
  
  if alternate_parent:
    parent = alternate_parent
    if parent.from_trunk_ref.key() not in path_trunk_set:
    
      path_trunk_set.add(parent.from_trunk_ref.key())
      path.append(parent.from_doc_ref)
      path_to_return = get_path_till_course(parent.from_doc_ref,
                                            path, path_trunk_set)
    else:
      path.reverse()
      path_to_return = [el.key() for el in path]
  else:
    path.reverse()
    path_to_return = [el.key() for el in path]

  return path_to_return


def get_or_create_session_id(widget, user):
  """Retrieves or creates a new session_id for the widget.
  
  Session id is assumed to be the key for WidgetProgressState entry 
  for the widget. We have separate model to store data for the user 
  per widget but since we need only one unique id we can reutilize 
  the id assigned by appstore instead of creating new one for 
  every sesssion. If no entry is present, a new entry is made. Currently,
  we are setting dirty bits to report stale scores.

  Args:
    widget: WidgetModel object for which session id is required.
    user: Associated user.
  Returns:
    returns key for the entry of corresponding WidgetProgressState model.
  """
  visit_state = models.WidgetProgressState.all().filter('user =', user).filter(
    'widget_ref =', widget).get()

  if not visit_state:
    visit_state = insert_with_new_key(models.WidgetProgressState, user=user,
                                      widget_ref=widget, progress_score=None)
  return str(visit_state.key())


def set_dirty_bits_for_doc(doc, user):
  """Sets dirty bit for all the parents in the path used to reach doc.

  Dirty bit indicates the score for the doc are stale and needs to be
  recomputed.
   
  TODO(mukundjha): We should check for the path, or pass path as 
  parameter.

  TODO(mukundjha): Maybe we should bind this with actual doc rather than
  trunk.

  Args:
    doc: Document for which score has just been updated.
    user: Associated user.
  """
  doc_visit_stack =  models.TraversalPath.all().filter(
      'current_trunk =', doc.trunk_ref).get()

  if not doc_visit_stack:
    return

  for el in doc_visit_stack.path:
    parent = db.get(el)
    visit_entry = models.DocVisitState.all().filter(
        'trunk_ref =', parent.trunk_ref).filter(
        'user =', user).get()
    if visit_entry:
      visit_entry.dirty_bit = True
      visit_entry.put()  
  

def update_visit_stack(doc, parent, user):
  """Updates the visit stack for a particular doc.

  Path appends parent to parent's path and sets as path for curernt doc.
  If parent is itself a course, only parent is added to the path as paths
  are rooted at course level.
 
  NOTE(mukundjha): Currently stack stores doc_ids, we could replace this with,
  trunk_id, doc_id, doc.title to reduce the datastore load.


  Args:
    doc: DocModel object for which visit stack is to be updated.
    parent: DocModel object - parent of the provided doc or None.
    user: Associated user.

  Returns:
    Updated visit stack entry object.
  """
  doc_visit_stack =  models.TraversalPath.all().filter(
      'current_trunk =', doc.trunk_ref).filter(
      'user =', user).get()

  if parent:
    if parent.label == models.AllowedLabels.COURSE:
      path = [parent.key()]
    else:
      parent_visit_stack = models.TraversalPath.all().filter(
          'current_trunk =', parent.trunk_ref).filter(
          'user =', user).get()
      if not parent_visit_stack:
        path_for_parent = get_path_till_course(parent)

        parent_visit_stack = insert_with_new_key(
            models.TraversalPath, current_trunk=parent.trunk_ref,
            current_doc=parent, path=path_for_parent, user=user)

      path = []
      cycle_detected = 0
      # Checking for loop
      for el in parent_visit_stack.path:
        element = db.get(el)
        if element.trunk_ref.key() == doc.trunk_ref.key():
          cycle_detected = 1
          break
        elif element.trunk_ref.key() == parent.trunk_ref.key():
          path.append(el)
          cycle_detected = 1
          break
        else:
          path.append(el)

      if not cycle_detected:
        path.append(parent.key())
      
    if doc_visit_stack:
      doc_visit_stack.path = path
      doc_visit_stack.put()
    else:
      doc_visit_stack = insert_with_new_key(
        models.TraversalPath, current_doc=doc, 
        current_trunk=doc.trunk_ref, path=path, user=user)
  
  # If parent is not present
  elif not doc_visit_stack:
    # Gets set of parents.
    path = get_path_till_course(doc)
    doc_visit_stack = insert_with_new_key(
        models.TraversalPath, current_trunk=doc.trunk_ref,
        current_doc=doc, path=path, user=user)
  return doc_visit_stack


def update_recent_course_entry(recent_doc, course, user):
  """Updates the entry for recent course visited/accesed.
  
  Note(mukundjha): instead of using course.get_score() we should
  use the get_accumulated_score() with recurse=True, but it would
  be too costly to do it on every update. Therefore its better to
  push the score-change/delta up the tree on every update.
  
  Args:
    recent_doc: Latest doc accessed for the course.
    course: Course to be updated.
    user: User for whom update is to be made.
  """
  # Update course entry only if the doc passed is a course.
  if course.label != models.AllowedLabels.COURSE:
    return None

  course_entry = models.RecentCourseState.all().filter('user =', user).filter(
      'course_trunk_ref =', course.trunk_ref).get()

  visit_state = models.DocVisitState.all().filter('user =', user).filter(
        'trunk_ref =', course.trunk_ref).get()

  if visit_state and visit_state.dirty_bit:
    doc_contents = get_doc_contents(course, user, resolve_links=True)
    score =  get_accumulated_score(course, user, doc_contents)
  else:
    score = course.get_score(user)

  if not course_entry:
    course_entry = insert_with_new_key(models.RecentCourseState,
                                       course_trunk_ref=course.trunk_ref,
                                       course_doc_ref=course,
                                       last_visited_doc_ref=recent_doc,
                                       course_score=score,
                                       user=user)
  else:
    course_entry.last_visited_doc_ref = recent_doc
    course_entry.course_doc_ref=course
    course_entry.course_score = score
    course_entry.put()
  return course_entry


def get_recent_in_progress_courses(user):
  """Gets a list of recent courses in progress. 
 
  Recomputes scores if score entry for course is stale.

  Args:
    user: User under consideration.
  
  Returns:
    List of recent course entry.
  """

  recent_list = models.RecentCourseState.all().filter('user =', user).order(
      '-time_stamp')
  in_progress = []
  num_to_pick = 5
  for entry in recent_list:
    visit_state = models.DocVisitState.all().filter('user =', user).filter(
        'trunk_ref =', entry.course_trunk_ref).get()

    if visit_state and visit_state.dirty_bit:
      course = fetch_doc(entry.course_trunk_ref.key())
      doc_contents = get_doc_contents(course, user, resolve_links=True)
      score =  get_accumulated_score(course, user, doc_contents)
      entry.course_score = score
      entry.put()
    else:
      score = entry.course_score
    
    if score < 100 and num_to_pick:
      num_to_pick -= 1
      in_progress.append(entry)
  
  return in_progress


def expand_path(path, user, use_history, absolute):
  """Expands the path into objects based on the parameters.

  Absolute is given preference over others.

  Args:
    path: List of doc_ids forming a traversal path.
    absolute: If set absolute addressing is used. Docs with same doc_ids in
      the list are fetched.
    user: User associated with request.
    use_history: If set then user's history is used to expand all
    the links.

  Returns:
    Returns list of DocModel objects corresponding to the doc_ids in the path 
    passed. 
  """
  path = [ db.get(el) for el in path ]
  if absolute:
    return path
  elif use_history:
    path = [ get_doc_for_user(el.trunk_ref.key(), user) for el in path ]
  else: 
    # Fetch latest
    path = [ fetch_doc(el.trunk_ref.key()) for el in path ]
  return path


def show_changes(pre, post):
  """Displays diffs between two models."""
  return pre.HtmlDiff(pre, post)


def get_doc_annotation(doc, user):
  """Retrieve annotation for a given doc.

  Args:
    doc: DocModel that is possibly annotated
    user: User in consideration
  Returns:
    A dictionary of { obj_id: annotation } for component documents in doc
  """
  if not isinstance(doc, models.DocModel) or (user is None):
    return None
  annotation = {}
  for el in doc.content:
    element = db.get(el)
    anno = (models.AnnotationState.all()
            .filter('user =', user)
            .filter('trunk_ref =', doc.trunk_ref)
            .filter('doc_ref =', doc)
            .filter('object_ref =', element))
    if anno.count() == 0:
      anno = models.AnnotationState(user=user,
                                    doc_ref=doc,
                                    trunk_ref=doc.trunk_ref,
                                    object_ref=element)
      anno.annotation_data = ""
      anno.put()
    else:
      anno = anno.get()
    annotation[str(element.key())] = {
        'data': anno.annotation_data,
        'key': str(anno.key()),
    }
  return annotation


def update_notes(name, data):
  """Update annotation data

  Args:
    name: key to AnnotationState
    data: new annotation data (serialized at the UI layer)
  """
  # NEEDSWORK(jch):
  # Since AnnotationState model wants annotation_data as serialized
  # blob of everything, the data here is opaque at this library layer
  # as the serialization is done between views layer and the JS in
  # the browser (and we probably do not want to do JSON at the library
  # layer).  This is somewhat awkward.  Perhaps AnnotationState should
  # be modified to learn logical fields as it grows???  I dunno.
  anno = db.get(name)
  anno.annotation_data = data.encode('utf-8')
  anno.put()


def get_notes(name):
  """Get annotation data on a given document

  Args:
    name: key to AnnotationState
  """
  anno = db.get(name)
  return anno.annotation_data


def view_doc_param(doc, visit, current, came_from):
  """Helper for what_now

  Args:
    doc: target document to go to
    visit: current visit stack
    current: current document (logically the tip of visit)
    came_from: document we are leaving from
  Returns:
    URL parameter to visit the doc, marking that it came from here
  """
  if not doc:
    return None

  param = [ ('trunk_id', str(doc.trunk_ref.key())),
            ('doc_id', str(doc.key())) ]

  if visit:
    l = len(visit.path) - 1

    while (0 < l) and (visit.path[l] != doc.key()):
      l -= 1
    if 0 < l:
      parent = db.get(visit.path[l - 1])
    elif l == 0:
      parent = None
    else:
      parent = current

    if parent:
      param.extend([ ('parent_trunk', str(parent.trunk_ref.key())),
                     ('parent_id', str(parent.key())) ])
  if came_from:
    param.extend([ ('came_from', str(came_from.key())) ])

  return param


def what_now(doc, visit, came_from):
  """Compute where to go next

  Args:
    doc: this document
    visit: traversal path from top to this document
    came_from: the document the user came from, when different from parent

  Returns:
    prev_param: URL parameters to feed to view to go to natural "previous" page
    next_param: URL parameters to feed to view to go to natural "next" page
  """
  prev_param = None

  # If we came back from down below, visit the next child (no "immediate
  # adjacency" required --- we have been showing this document already).
  # If we came from top-down navigation, we do not have came_from; visit
  # the first child in that case, and pretend as if the user just navigated
  # in the usual top-down fashion (i.e. no need for came_from).
  next = doc.first_child_after(came_from)
  next_came_from = None

  here = doc
  if (not next) and visit and visit.path:
    # We ran out of our children, so go back to our parent.
    # visit.path should be the path from the root down to doc.

    l, child = len(visit.path), doc
    while (0 < l):
      l -= 1
      parent = db.get(visit.path[l])
      # After visiting child inside parent, "next_child_or_self" is either
      # the target of a link to the child that immediately follows the
      # link to this child, or the parent itself if the link to this child
      # is followed by a non-link material, or None which tells us to
      # ask the grandparent what to do.
      next = parent.next_child_or_self(child)

      if next:
        if next == parent:
          # parent has a non-link after the link to this child
          # revisit the parent to show that non-link, and remember
          # to visit the link after that child
          next_came_from = child
        else:
          # following the link to the next child, as if we came
          # directly from the top
          next_came_from = None
        here = parent
        break
      else:
        child = parent

  next_param = view_doc_param(next, visit, here, next_came_from)

  return (prev_param, next_param)
