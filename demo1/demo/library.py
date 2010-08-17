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
#  remainder = num_chars % 4
#  num_bytes = ((num_chars + remainder) / 4) * 3
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


def get_score_for_link(link_element, user, recurse=False):
  """Cacluates score for the DocLink object by selecting 
  correct document based on user's history.

  NOTE(mukundjha): This function is defined because get_score
  for DocLink model uses absolute address for the link and does
  not incorporate user's history. Function get_score for DocLink could have
  been modified, but it is counter intuitive.

  *It is slightly inefficient, because it recomputes score 
  everytime, even if they have recently been updated.

  *Does not take care of cycles.

  Args:
    link_element: Link object for which score is required.
    user: User whose score is desired.
    recurse: If set True, all the scores will be recursively computed
      and updated.

  Returns: 
    Score for the link object.
  """
  doc = link_element.doc_ref
  if recurse:
    doc_contents = get_doc_contents(doc, True, False, user, False)
    return get_accumulated_score(doc, doc_contents, user, False, recurse)
  else:
    visit_state = models.DocVisitState.all().filter('user =', user).filter(
    'trunk_ref =', doc.trunk_ref).get()
    if visit_state and visit_state.dirty_bit:
      doc_contents = get_doc_contents(doc, False, False, user, False)
      return get_accumulated_score(doc, doc_contents, user, False, recurse)
    elif visit_state:
      return visit_state.progress_score
    else:
      return 0


def get_accumulated_score(doc, doc_contents, user, use_history=False, recurse=False):
  """Calculate score for a doc by accumulating scores from its objects.
  
  Assumption if doc_contents contain score for docLinkElement, it is resolved
  using correct parameters and is preferred over recalculation.
  Averages score, no weights. It also updates the score for element.

  Args:
    doc: Document fetching the score.
    doc_contents: List of objects referenced in list of contents of the doc.
      the list is passed separately to prevent repeated calls to data-store
      for objects.
    user: User associated with the score.
    recurse: If set True scores are recursively re-computed instead of just
      picking entries from datastore.
  Returns:
    Average score based on content of the document. Also adds score attribute
    to each 'scorable' element.
  """
  total, count = 0,0
  for element in doc_contents:
    if not isinstance(element, models.DocLinkModel): 
      element.score = element.get_score(user)
    else:
      element.score = get_score_for_link(element, user, recurse)

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
      trunk_ref=doc.trunk_ref.key(), doc_ref=doc.key(), progress_score= score)


def get_doc_contents(doc, resolve_links, use_history, user, fetch_score):
  """Return a list of objects referred by keys in content list of a doc.

  NOTE(mukundjha): doc is a DocModel object and not an id.
  Args:
    doc: DocModel used for populating content objects.
    reslove_links: If reslove_links is true, then links are resolved to
      get appropriate title for links.
    use_history: Use history to resolve links.
    user: User in consideration.
    fetch_score: If set true score is also appended to all objects.
  Returns:
    An ordered list of objects referenced in content list of passed doc.
  Raises:
    BadKeyError: If element referred is invalid.
  """
  if not isinstance(doc, models.DocModel):
    return None
  else:
    content_list = []
    for el in doc.content:
      element = db.get(el)
      if not isinstance(element, models.DocLinkModel):
        if fetch_score:
          element.score = element.get_score(user)
        if isinstance(element, models.WidgetModel):
          temp_array = re.split('/',re.sub('//','__TEMP__', element.widget_url))
          base_url = re.sub('__TEMP__','//',temp_array[0])
          element.base_url = base_url + '/'
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
            .filter('user=', user).filter('doc_ref=', doc)
            .filter('object_ref=', element)).get()
    if not anno or not anno.annotation_data:
      if 1:
	anno = models.AnnotationState(user=user, doc_ref=doc, object_ref=element)
	anno.annotation_data = ("Sample Annotation Given To %s" %
                                element.asText()[:40])
	anno.put()
    annotation[str(element.key())] = anno.annotation_data
  return annotation


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

  parent_entry = models.DocLinkModel.all().filter('trunk_ref =', doc.trunk_ref).order(
      '-created').fetch(1000)
  # Set if an alternate path is picked for a case where cycle is found.
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
          logging.info(
              'PARENTLISTPATH LOOP1***\n adding %r to list %r \nand %r to trunk %r\n',
              parent.from_doc_ref.title, [p.title for p in path],
              parent.from_trunk_ref.key(), path_trunk_set)

          path_trunk_set.add(parent.from_trunk_ref.key())
          path.append(parent.from_doc_ref)
          path.reverse()
          path_to_return = [el.key() for el in path]
          logging.info('RETURNING PATH LOOP 1: %r',  [p.title for p in path])
          return path_to_return
     
  
  if alternate_parent:
    parent = alternate_parent
    if parent.from_trunk_ref.key() not in path_trunk_set:
    
      logging.info('PARENTLISTPATH LOOP2** adding %r to list %r \nand %r to trunk %r\n',
                   parent.from_doc_ref.title, [p.title for p in path],
                   parent.from_trunk_ref.key(), path_trunk_set)
      path_trunk_set.add(parent.from_trunk_ref.key())
      path.append(parent.from_doc_ref)
      logging.info('****Path sent %r', path) 
      path_to_return = get_path_till_course(parent.from_doc_ref, path, path_trunk_set)
    else:
      path.reverse()
      path_to_return = [el.key() for el in path]
  else:
    path.reverse()
    path_to_return = [el.key() for el in path]

  logging.info('RETURNING PATH LOOP 2: %r',  [p.title for p in path])
  return path_to_return


def get_or_create_session_id(widget, user):
  """Retrieves or creates a new session_id for the widget.
  
  Session id is assumed to be the key for WidgetProgressState entry 
  for the widget. We have separate model to store data for the user 
  per widget but since we need only one unique id we can reutilize 
  the id assigned by appstore instead of creating new one for 
  every sesssion. If no entry is present, a new entry is made.

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
      'current_trunk =', doc.trunk_ref).get()

  if parent:
    if parent.label == models.AllowedLabels.COURSE:
      path = [parent.key()]
    else:
      parent_visit_stack = models.TraversalPath.all().filter(
          'current_trunk =', parent.trunk_ref).get()
      if not parent_visit_stack:
        path_for_parent = get_path_till_course(parent)

        parent_visit_stack = insert_with_new_key(
            models.TraversalPath, current_trunk=parent.trunk_ref,
            current_doc=parent, path=path_for_parent)

      path = []
      cycle_detected = 0
      # Checking for loop
      for el in parent_visit_stack.path:
        element = db.get(el)
        if element.trunk_ref.key() == doc.trunk_ref.key():
          cycle_detected = 1
          logging.info("\n************DOC CYCLE DETECTED ****************\n")
          break
        elif element.trunk_ref.key() == parent.trunk_ref.key():
          path.append(el)
          cycle_detected = 1
          logging.info("\n************PARENT CYCLE DETECTED ****************\n")
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
        current_trunk=doc.trunk_ref, path=path)
  
  # If parent is not present
  elif not doc_visit_stack:
    # Gets set of parents.
    path = get_path_till_course(doc)
    doc_visit_stack = insert_with_new_key(
        models.TraversalPath, current_trunk=doc.trunk_ref,
        current_doc=doc, path=path)
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
  logging.info('*********UPDATING RECENT COURSE ENTRY #******* %r %r %r', course.title, user, course.label)
  if course.label != models.AllowedLabels.COURSE:
    logging.error('FUNCTION:update_recent_course_entry- Doc passed not a course')
    return None
  course_entry = models.RecentCourseState.all().filter('user =', user).filter(
      'course_trunk_ref =', course.trunk_ref).get()
  #getting the latest accessed course
  course = get_doc_for_user(course.trunk_ref.key(), user)

  if not course_entry:
    course_entry = insert_with_new_key(models.RecentCourseState,
                                       course_trunk_ref=course.trunk_ref,
                                       course_doc_ref=course,
                                       last_visited_doc_ref=recent_doc,
                                       course_score=course.get_score(user),
                                       user=user)
  else:
    course_entry.last_visited_doc_ref = recent_doc
    course_entry.course_doc_ref=course
    course_entry.course_score = course.get_score(user)
    logging.info('*******COURSE SCORE %r', course.get_score(user))
    course_entry.put()
  return course_entry


def get_recent_in_progress_courses(user):
  """Gets a list of recent courses in progress.

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
    logging.info('****** %r %r', entry, entry.course_score)
    if entry.course_score < 100 and num_to_pick:
      num_to_pick -= 1
      in_progress.append(entry)
      logging.info('****** picked %r', entry)
  
  return in_progress


def expand_path(path, use_history, absolute, user):
  """Expands the path into objects based on the parameters.

  Absolute is given preference over others.
  Args:
    path: List of doc_ids forming a traversal path.
    use_history: If set then user's history is used to expand all
    the links.
    absolute: If set absolute addressing is used. Docs with same doc_ids in
      the list are fetched.
    user: User associated with request.
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
