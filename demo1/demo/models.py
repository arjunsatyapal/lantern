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

# gql() and Account is heavily based on the one from rietveld:
#
#  http://code.google.com/p/rietveld
#

"""App Engine data model (schema) definition for Lantern."""

# Python imports
import base64
import datetime
import difflib
import itertools
import logging
import md5
import operator
import os
import random
import re
import sha
import string
import time

# AppEngine imports
from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import users

# Local imports
import constants
import htmlfolder

### GQL query cache ###


_query_cache = {}


def gql(cls, clause, *args, **kwds):
  """Return a query object, from the cache if possible.

  Args:
    cls: a db.Model subclass.
    clause: a query clause, e.g. 'WHERE draft = TRUE'.
    *args, **kwds: positional and keyword arguments to be bound to the query.

  Returns:
    A db.GqlQuery instance corresponding to the query with *args and
    **kwds bound to the query.
  """
  query_string = 'SELECT * FROM %s %s' % (cls.kind(), clause)
  query = _query_cache.get(query_string)
  if query is None:
    _query_cache[query_string] = query = db.GqlQuery(query_string)
  query.bind(*args, **kwds)
  return query


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


def insert_model_with_new_key(cls, parent=None, **kwargs):
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


class Account(db.Model):
  """Maps a user or email address to a user-selected nickname, and more.

  NOTE(vche): Changed from rietveld to use user_id, rather than email,
  as the key, since the user_id is more stable.

  Nicknames do not have to be unique.

  The default nickname is generated from the email address by
  stripping the first '@' sign and everything after it.  The email
  should not be empty nor should it start with '@' (AssertionError
  error is raised if either of these happens).

  This also holds a list of ids of starred issues.  The expectation
  that you won't have more than a dozen or so starred issues (a few
  hundred in extreme cases) and the memory used up by a list of
  integers of that size is very modest, so this is an efficient
  solution.  (If someone found a use case for having thousands of
  starred issues we'd have to think of a different approach.)
  """

  user = db.UserProperty(auto_current_user_add=True, required=True)
  user_id = db.StringProperty(required=True)  # key == <user_id>
  email = db.EmailProperty(required=True)
  nickname = db.StringProperty(required=True)
  created = db.DateTimeProperty(auto_now_add=True)
  modified = db.DateTimeProperty(auto_now=True)
  stars = db.ListProperty(str)  # key names of all starred modules.
  fresh = db.BooleanProperty()

  # Current user's Account.  Updated by middleware.AddUserToRequestMiddleware.
  current_user_account = None

  lower_email = db.StringProperty()
  lower_nickname = db.StringProperty()
  xsrf_secret = db.BlobProperty()

  # Note that this doesn't get called when doing multi-entity puts.
  def put(self):
    self.lower_email = str(self.email).lower()
    self.lower_nickname = self.nickname.lower()
    super(Account, self).put()

  @classmethod
  def get_account_for_user(cls, user):
    """Get the Account for a user, creating a default one if needed."""
    user_id = user.user_id()
    email = user.email()
    assert user_id
    key = '<%s>' % user_id
    # Since usually the account already exists, first try getting it
    # without the transaction implied by get_or_insert().
    account = cls.get_by_key_name(key)
    if account is not None:
      return account
    nickname = cls.create_nickname_for_user(user)
    return cls.get_or_insert(key, user=user, user_id=user_id, email=email,
                             nickname=nickname, fresh=True)

  @classmethod
  def create_nickname_for_user(cls, user):
    """Returns a unique nickname for a user, appending numeric suffix."""
    name = nickname = user.email().split('@', 1)[0]
    next_char = chr(ord(nickname[0].lower())+1)
    existing_nicks = [account.lower_nickname
                      for account in cls.gql(('WHERE lower_nickname >= :1 AND '
                                              'lower_nickname < :2'),
                                             nickname.lower(), next_char)]
    suffix = 0
    while nickname.lower() in existing_nicks:
      suffix += 1
      nickname = '%s%d' % (name, suffix)
    return nickname

  @classmethod
  def get_nickname_for_user(cls, user):
    """Get the nickname for a user."""
    return cls.get_account_for_user(user).nickname

  @classmethod
  def get_email_for_user(cls, user):
    """Get the email for a user."""
    return cls.get_account_for_user(user).email

  @classmethod
  def get_account_for_id(cls, user_id):
    """Get the Account for a user id, or return None."""
    assert user_id
    key = '<%s>' % user_id
    return cls.get_by_key_name(key)

  @classmethod
  def get_by_key_name(cls, key, **kwds):
    """Override db.Model.get_by_key_name() to use cached value if possible."""
    if not kwds and cls.current_user_account is not None:
      if key == cls.current_user_account.key().name():
        return cls.current_user_account
    return super(Account, cls).get_by_key_name(key, **kwds)

  @classmethod
  def get_nickname_for_id(cls, user_id, default=None):
    """Get the nickname for a user id, possibly a default.

    If default is None a generic nickname is computed from the id.

    Args:
      user_id: User's account id.
      default: If given and no account is found, returned as the default value.
    Returns:
      Nickname for given email.
    """
    account = cls.get_account_for_id(user_id)
    if account is not None and account.nickname:
      return account.nickname
    if default is not None:
      return default
    return 'user_' + user_id

  @classmethod
  def get_accounts_for_email(cls, email):
    """Get list of Accounts that have this email."""
    assert email
    return [a for a in cls.all().filter('lower_email =', email.lower())]

  @classmethod
  def get_accounts_for_nickname(cls, nickname):
    """Get the list of Accounts that have this nickname."""
    assert nickname
    assert '@' not in nickname
    return [a for a in cls.all().filter('lower_nickname =', nickname.lower())]

  @classmethod
  def get_nickname_for_email(cls, email, default=None):
    """Get the nickname for an email, possibly a default.

    If default is None a generic nickname is computed from the email
    address.

    Args:
      email: User's email.
      default: If given and no account is found, returned as the default value.
    Returns:
      Nickname for given email.
    """
    accounts = cls.get_accounts_for_email(email)
    if accounts:
      account = None
      if isinstance(accounts, list):
        account = accounts[0]
      if account.nickname:
        return account.nickname
    if default is not None:
      return default
    return email.replace('@', '_')

  @classmethod
  def get_email_for_nickname(cls, nickname):
    """Turn a nickname into an email address.

    If the nickname is not unique or does not exist, this returns None.
    """
    accounts = cls.get_accounts_for_nickname(nickname)
    if not accounts:
      return None
    return accounts[0].email

  def user_has_selected_nickname(self):
    """Return True if the user picked the nickname.

    Normally this returns 'not self.fresh', but if that property is
    None, we assume that if the created and modified timestamp are
    within 2 seconds, the account is fresh (i.e. the user hasn't
    selected a nickname yet).  We then also update self.fresh, so it
    is used as a cache and may even be written back if we're lucky.
    """
    if self.fresh is None:
      delta = self.created - self.modified
      # Simulate delta = abs(delta)
      if delta.days < 0:
        delta = -delta
      self.fresh = (delta.days == 0 and delta.seconds < 2)
    return not self.fresh

  def get_xsrf_token(self, offset=0):
    """Return an XSRF token for the current user."""
    if not self.xsrf_secret:
      self.xsrf_secret = os.urandom(8)
      self.put()
    m = md5.new(self.xsrf_secret)
    email_str = self.lower_email
    if isinstance(email_str, unicode):
      email_str = email_str.encode('utf-8')
    m.update(self.lower_email)
    when = int(time.time()) // 3600 + offset
    m.update(str(when))
    return m.hexdigest()


class ProvisionalAccount(db.Model):
  """Account based on email only, before user has logged in.

  This is used to inviting someone that has not logged into Lantern yet.

  Attributes:
    email: The email to use for the account.
    real_account: References the real account when it is created.
    created: The date/time that the account was created.
    modified: The date/time that the account was modified.
  """

  email = db.EmailProperty(required=True)
  created = db.DateTimeProperty(auto_now_add=True)
  modified = db.DateTimeProperty(auto_now=True)
  real_account = db.ReferenceProperty(Account)

  lower_email = db.StringProperty()

  # Note that this doesn't get called when doing multi-entity puts.
  def put(self):
    self.lower_email = str(self.email).lower()
    super(ProvisionalAccount, self).put()

  @classmethod
  def get_accounts_for_email(cls, email, expiration_days=30):
    """Get list of Accounts that have this email.

    Args:
      email: Email address to use for lookup.
      expiration_days: If non-zero, returns accounts that were created within
          the specified number of days.
    Returns:
      A list of matching accounts. It may be an empty list.
    """
    assert email
    query = cls.all().filter('lower_email =', email.lower())
    if expiration_days:
      dt = datetime.datetime.now() - datetime.timedelta(days=expiration_days)
      query.filter('created >', dt).order('-created').order('-modified')
    return [a for a in query]

  @classmethod
  def get_or_create_account_for_email(cls, email):
    """Create a new temporary account for the specified email."""
    assert email
    accounts = cls.get_accounts_for_email(email)
    if not accounts:
      account = insert_model_with_new_key(cls, email=email, nickname='')
    else:
      # Just returns the first match.
      account = accounts[0]
    return account


class InvalidTrunkError(Exception):
  """Exception raised for invalid trunk access."""


class InvalidDocumentError(Exception):
  """Exception raised when invalid document access."""


class InvalidElementError(Exception):
  """Exception raised when invalid document access."""


class InvalidQuizError(Exception):
  """Exception raised for invalid quiz access."""


class InvalidWidgetError(Exception):
  """Exception raised for invalid widget access."""


class BaseModel(db.Model):
  """Abstract base class inherited by all Lantern models."""

  @classmethod
  def insert_with_new_key(cls, parent=None, **kwargs):
    """Generates a random key, making sure it's not in the current database.

    Args:
      cls: Model class;
      parent: add models to the entyty group of this parent;
      kwargs: The initial values for the required fields;

    Returns:
      The newly inserted object.
    """
    return insert_model_with_new_key(cls, parent=parent, **kwargs)


class UserStateModel(db.Model):
  """Abstract base class for all user specific state models.

  Attributes:
    user: Reference to the the user.
  """
  user = db.UserProperty(auto_current_user_add=True, required=True)


class BaseContentModel(BaseModel):
  """Abstract base class inherited by all immutable content objects.

  Immutable objects like DocModel, TrunkModel, VideoModel etc.

  Attributes:
    creator: Author of the content.
    created: Time of creation.
  """
  creator = db.UserProperty(auto_current_user_add=True, required=True)
  created = db.DateTimeProperty(auto_now_add=True)

  @classmethod
  def insert(cls, **kwargs):
    """Creates a new object if not already exists, else returns the
    existing object based on content of the object.

    Inserts with SHA1 hash of the concatenated contents key_name,
    if object already exists with same content, that object is
    returned, else a new object is created (using the keyword args to
    set the initial property values) and returned.

    TODO(mukundjha): Add some random seed as well to prevent collision.
    Args:
      cls: Class for which object is to be created.
      kwargs: The keyword args represents property values for the model.
          These are intended to be the properties that uniquely identify an
          instance of the model. The default implementation requires that
          each are matches a defined property of the model. Derived classes
          may override _get_identifying_fields() to allow "identifier" fields
          that are not stored in the model. See WidgetModel for details.

    Returns:
      Returns an object of type cls.
    """
    identifying_fields = cls._get_identifying_fields(**kwargs)
    txt = '|'.join(identifying_fields)

    key_name = cls.__name__ + ':' + sha.new(txt).hexdigest()
    object = cls.get_by_key_name(key_name)

    if not object:
      object = cls.get_or_insert(key_name, **kwargs)
    return object

  @classmethod
  def _get_identifying_fields(cls, **kwargs):
    """Gets a list of fields that uniquely identify an entry.

    The fields are used to generate a hash to form the key name.
    The default implementation expects each keyword arg be a valid property
    of the model. Derived classes (e.g., WidgetModel) can override to allow
    properties that are stored in the model.

    Args:
      kwargs: Specifies the property values of the model as keyword args.
    """
    fields = []
    for prop in sorted(cls.properties()):
      if prop in ('creator', 'created'):  # Skip base properties
        continue
      v = kwargs.get(prop)
      if isinstance(v, unicode):
        v = v.encode('utf-8')
      fields.append(str(v))
    return fields

  def get_score(self, user):
    """Returns progress score for the model.
    Function returns None by default and must be over-ridden by
    subclasses to return any other valid score.

    Args:
     user: User whose score is fetched.
    Returns:
     Score for the model or None if not scorable.
    """
    return None

  def asText(self):
    """Return textual representation for diffing and merging"""
    # Fallback implementation
    return "%s: %s" % (self.__class__.__name__, self.ident())

  def ident(self):
    """Fallback implementation for identifying this object to the end user"""
    return "%s" % id(self)

  def metainfo(self, full=0):
    """A list of (label, string) tuples to describe the document

    Subclasses can add their own metainformation by overriding
    myMetainfo() method.
    """
    if full:
      return ([('Creator', self.creator),
               ('Created', self.created)] +
              self.myMetainfo())
    return (self.myMetainfo())

  def metainfoOneline(self, full=0):
    """self.metainfo() in a one-line-per-item format, used in UI."""
    return ['%s: %s' % elem for elem in self.metainfo(full)]

  def metainfoHtml(self, full=0):
    """self.metainfoOneline() in HTML format, used in UI"""
    return "\n".join(["<div>%s</div>" %
                      elem for elem in self.metainfoOneline(full)])

  def myMetainfo(self):
    """Subclass specific enhancement to self.metainfo(), to be overriden."""
    return [] # override

  @classmethod
  def HtmlDiff(cls, one, two, context=True):
    """Return diff to turn one into two.

    This is implemented as a classmethod so that a creation patch can be
    sanely requested by the caller (e.g. DocModel.HtmlDiff(None, newrev)).
    """
    # Fallback implementation
    if two is None:
      if one is None:
        # Should not happen but wth...
        return ""
      return ('<div class="diff_delete">%s%s</div>' %
              (one.metainfoHtml(full=1), one.asText()))
    elif one is None:
      return ('<div class="diff_insert">%s%s</div>' %
              (two.metainfoHtml(full=1), two.asText()))

    onetext = "\n".join(one.metainfoOneline()) + one.asText()
    twotext = "\n".join(two.metainfoOneline()) + two.asText()
    if onetext == twotext:
      return ""
    differ = difflib.HtmlDiff()
    return differ.make_table(one.metainfoOneline() + one.asText().split("\n"),
                             two.metainfoOneline() + two.asText().split("\n"),
                             fromdesc="Previous",
                             todesc="This Version",
                             context=context)


class ObjectType(object):
  """Stores constant string defining type of different data models."""
  DOC = 'doc'
  VIDEO = 'video'
  QUIZ = 'quiz'
  RICH_TEXT = 'rich_text'
  PY_SHELL = 'py_shell'
  TRUNK = 'trunk'
  DOC_LINK = 'doc_link'
  WIDGET = 'widget'
  NOTEPAD = 'notepad'

class AllowedLabels(object):
  """Stores constants string defining various allowed labels for DocModel."""
  MODULE = 'MODULE'
  LESSON = 'LESSON'
  COURSE = 'COURSE'

  @classmethod
  def dump_to_list(self):
    """Dumps all the allowed types."""
    return ['MODULE', 'LESSON', 'COURSE']


class DocModel(BaseContentModel):
  """Representation of a document.

  Document is essentially a collection of ordered objects with an associated
  revision history.

  Attributes:
    trunk_ref: Reference to the associated trunk.
    title: Title associated with the document.
    predecessors: Pointers to the predecessor document in revision chain.
    Mulitple predecessor will exist when we merge two different trunks or
    import from two different modules.
    grade_level: Grade level associated with the doc.
    tags: Set of tags (preferably part of some ontology).
    content: Ordered list of references to objects/items as it appears in
      the document.
    label: Label marks document as course, module or lesson.
    score_weight: It's a list defining weight each content element contributes
      towards the score. By default all scorable elements are given equal
      weight. But this is a provision for later.

  TODO(mukundjha): Add required=True for required properties.
  """
  trunk_ref = db.ReferenceProperty(reference_class=None)
  # implicit doc_id
  title = db.StringProperty(required=True, default='Add a title')
  tags = db.ListProperty(db.Category)
  predecessors = db.ListProperty(db.Key)
  grade_level = db.IntegerProperty(default=constants.DEFAULT_GRADE_LEVEL)
  content = db.ListProperty(db.Key)
  label = db.StringProperty(default=AllowedLabels.MODULE)
  score_weight = db.ListProperty(float)

  def get_score(self, user):
    """Returns progress score for the doc.

    Looks up the DocVisitState for the score.

    Args:
     user: User whose score is fetched.
    Returns:
     Score for the doc.
    Raises:
     InvalidDocumentError: If doc is invalid.
    """
    visit_state = DocVisitState.all().filter('user =', user).filter(
      'trunk_ref =', self.trunk_ref).order('-last_visit').get()

    if visit_state:
      return visit_state.progress_score
    else:
      return 0

  def insert_after(self, old, new):
    """Insert a link to the new document immediately after the link to the old.

    Args:
      old: old document
      new: new document
    """
    content_len = len(self.content)
    old_key = str(old.key())
    for i, element in enumerate(self.content):
      elem = db.get(element)
      if not isinstance(elem, DocLinkModel):
        continue
      doc = elem.doc_ref
      if not doc:
        continue
      doc_key = str(doc.key())
      if doc_key == old_key:
        break
    else:
      return # not found

    link_to_new = DocLinkModel.insert_with_new_key(
        trunk_ref=new.trunk_ref,
        doc_ref=new,
        from_trunk_ref=self.trunk_ref,
        from_doc_ref=self)

    self.content.insert(i + 1, link_to_new.key())
    self.put()

  # Match titles "Basic Algebra #1" or "Section 12" but not "Python3";
  # $1 = text before the number
  # $2 = number
  _NUMBERED_TITLE_RE = re.compile(r'^(.*?\W)(\d+)$')

  # Match "Clone (3) of Trigometry";
  # $1 = title text
  # $2 = number
  _CLONED_TITLE_RE = re.compile(r'^Clone \((\d+)\) of (.*)')

  def _clone_title(self, title):
    """Compute an appropriate title for a cloned element"""
    m = self._NUMBERED_TITLE_RE.match(title)
    if m:
      return '%s%d' % (m.group(1), int(m.group(2)) + 1)
    m = self._CLONED_TITLE_RE.match(title)
    if m:
      return 'Clone (%d) of %s' % (int(m.group(1)) + 1, m.group(2))
    return 'Clone (1) of %s' % title

  def setClonedTitle(self):
    self.title = self._clone_title(self.title)

  def clone(self):
    """Create a shallow copy of self"""
    cloned = DocModel.insert_with_new_key()
    for attr in DocModel.properties():
      try:
        v = getattr(self, attr)
      except AttributeError:
        continue
      setattr(cloned, attr, v)
    return cloned

  def placeInNewTrunk(self, creator=None):
    """Make a new trunk and make this the latest/sole incarnation

    Args:
      creator: Allows specifying creator explicitly.

    Returns:
      A new TrunkModel object
    """
    creator = creator or users.get_current_user()
    doc_id = str(self.key())
    trunk = TrunkModel.insert_with_new_key(creator=creator)
    trunk.setHead(self)
    trunk.put()
    self.trunk_ref = trunk
    TrunkRevisionModel.insert_with_new_key(
        creator=creator, parent=trunk, obj_ref=doc_id, commit_message='Cloned')
    self.put()
    return trunk

  def updateTrunkHead(self, other, message=''):
    """Update the trunk to make 'other' the latest incarnation of 'self'

    Args:
      other: another DocModel
    Returns:
      a new TrunkModel object
    """
    doc_id = str(other.key())
    trunk = self.trunk_ref
    trunk.setHead(other)
    trunk.put()
    other.trunk_ref = trunk
    other.put()
    TrunkRevisionModel.insert_with_new_key(
        parent=trunk, obj_ref=doc_id, commit_message=message)
    return trunk

  def trunk_tip(self):
    """Returns the tip of the same trunk"""
    return db.get(self.trunk_ref.head)

  def dump_to_dict(self):
    """Returns all attributes of the doc object in a dictionary.

    Each attribute is keyed with doc_attribute_name and a special element
    'obj_type' denotes the kind of model it is. This could be useful for
    rendering different kind of objects.
    """
    # Not sure we should convert all list elements to str
    data_dict = {
      'obj_type': ObjectType.DOC,
      'doc_title': self.title,
      'doc_tags': self.tags,
      'doc_predecessors': self.predecessors,
      'doc_grade_level': str(self.grade_level),
      'doc_creator': str(self.creator),
      'doc_created': str(self.created),
      'doc_label': self.label
      }

    if self.trunk_ref:
      data_dict['doc_trunk_ref'] = str(self.trunk_ref.key())
    # collecting content
    content_list = []

    for element_key in self.content:
      element = db.get(element_key)
      if element:
        content_list.append(element.dump_to_dict())
      else:
        raise InvalidElementError("Element with key not found " +
          str(element_key))

    data_dict['doc_content'] = content_list
    return data_dict

  def first_child_after(self, child):
    """Return the target of the first link after a link pointing to the child"""
    if child:
      skip_until = str(db.get(child.trunk_ref.head).key())
    else:
      skip_until = None
    for el in self.content:
      elem = db.get(el)
      if not isinstance(elem, DocLinkModel):
        continue
      tip = db.get(elem.doc_ref.trunk_ref.head)
      if not skip_until:
        return tip
      if skip_until == str(tip.key()):
        skip_until = None
    return None

  def next_child_or_self(self, child):
    """Return the next child if a link to one follows immediately to link to child

    We have visited 'child' which is a document pointed at by a DocLink
    in self.  If the DocLink is immediately followed by another DocLink,
    follow that DocLink.  If the DocLink is followed by a non-link, we
    need to show ourselves again, so return self.  If the DocLink to the
    child is the last element in self, return None to tell the caller to
    look in our parent.
    """
    skip_until = str(db.get(child.trunk_ref.head).key())
    for el in self.content:
      elem = db.get(el)
      if not isinstance(elem, DocLinkModel):
        # Have we seen child?
        if not skip_until:
          return self
        continue
      tip = db.get(elem.doc_ref.trunk_ref.head)
      if not skip_until:
        return tip
      if skip_until == str(tip.key()):
        skip_until = None
    return None

  def metainfo(self, full=0):
    # As DocModel is the toplevel, we ignore "full=0" and always
    # give the creator information
    return ([('Creator', self.creator),
             ('Created', self.created)] +
            self.myMetainfo())

  def myMetainfo(self):
    return [('Title', self.title)]

  @classmethod
  def HtmlDiff(cls, one, two, context=True):
    if two is None:
      if one is None:
        # Should not happen but wth...
        return ""
      return ('<div class="diff_delete">%s%s</div>' %
              (one.metainfoHtml(full=1), one.asText()))
    elif one is None:
      return ('<div class="diff_insert">%s%s</div>' %
              (two.metainfoHtml(full=1), two.asText()))

    # Both are DocModel with content[]
    oneContent = one.contentAsComparable()
    twoContent = two.contentAsComparable()

    # First compare them at the surface level
    ops = list(difflib.SequenceMatcher(None, oneContent, twoContent).
               get_opcodes())

    # Decompose "replace" into "delete" then "insert"
    oplist = []
    for op in ops:
      (tag, i1, i2, j1, j2) = op
      if tag == 'replace':
        oplist.extend([('delete', i1, i2, j1, j1),
                       ('insert', i1, i1, j1, j2)])
      else:
        oplist.append(op)

    result = []
    differ = difflib.HtmlDiff()
    onetext = "\n".join(one.metainfoOneline())
    twotext = "\n".join(two.metainfoOneline())
    if onetext != twotext:
      result.append(differ.make_table(one.metainfoOneline(),
                                      two.metainfoOneline(),
                                      fromdesc="Previous",
                                      todesc="This Version",
                                      context=context))

    for (tag, i1, i2, j1, j2) in oplist:
      if tag == 'delete':
        for i in range(i1, i2):
          this = oneContent[i].doc
          result.append(this.HtmlDiff(this, None))
      elif tag == 'insert':
        for j in range(j1, j2):
          that = twoContent[j].doc
          result.append(that.HtmlDiff(None, that))
      elif tag == 'equal':
        for (i, j) in itertools.izip(range(i1, i2), range(j1, j2)):
          this = oneContent[i].doc
          that = twoContent[j].doc
          result.append(this.HtmlDiff(this, that))
      else:
        "Should not happen (seen tag '%s')" % tag

    return "<div>" + "</div>\n<div>".join(result) + "</div>"

  def contentAsComparable(self):
    return [ComparableSequenceElem(db.get(elem)) for elem in self.content]

  def outline(self):
    """Return outline of the document and its subdocuments"""
    page = { 'doc_id': str(self.key()),
             'trunk_id': str(self.trunk_ref.key()),
             'title': self.title,
             'content': [],
             }
    try:
      content_list = db.get(self.content)
    except db.BadKeyError:
      content_list = []
      for content_id in self.content:
        try:
          content = db.get(content_id)
          content_list.append(content)
        except BadKeyError:
          pass

    for doclink in content_list:
      if (not doclink) or (not isinstance(doclink, DocLinkModel)):
        continue
      try:
        target = db.get(doclink.trunk_ref.head)
      except (BadKeyError, AttributeError):
        target = None
      if (not target) or (not isinstance(target, DocModel)):
        continue
      page['content'].append(target.outline())
    return page


class TrunkModel(BaseModel):
  """Represents a trunk.

  Trunk keeps track of revisions made to a document. Each document must
  be associated with one trunk.

  Attributes:
     head: Pointer to a document representing current version of the trunk.
       This is stored as string to allow atomic transcations while adding
       and creating new trunks/documents.
     fork_list: List of trunks formed by forking from this trunk.
     fork_commit_messages: Commit message log for each fork instance.
  """
  # implicit key
  # Probably we need another model to keep fork_list
  head = db.StringProperty()
  title = db.StringProperty()
  fork_list = db.ListProperty(db.Key)
  fork_commit_messages = db.StringListProperty()

  def dump_to_dict(self):
    """Returns all attributes of the object in a dictionary."""
    return {
      'obj_type': ObjectType.TRUNK,
      'trunk_fork_list': self.fork_list,
      'trunk_fork_commit_messages': self.fork_commit_messages
      }

  def setHead(self, doc_or_id):
    """Update the trunk head.

    Trunk caches some information on the document at its tip, and
    here is the place to update it.  Do not use trunk.head = doc_id directly.

    Args:
      doc_or_id: A DocModel or an id referencing a DocModel.
    """
    if isinstance(doc_or_id, basestring):
      self.head = doc_or_id
      try:
        doc = db.get(doc_or_id)
      except (db.BadKeyError, db.BadRequestError):
        # library.createnewdoc runs this inside a transaction
        # and updating doc and trunk at the same time will throw
        # an exception (different entity groups).
        # the caller will take care of updating the title in that case.
        return
    elif isinstance(doc_or_id, DocModel):
      doc = doc_or_id
      self.head = str(doc.key())
    else:
      # Unexpected input type. Ignore.
      return
    if isinstance(doc, DocModel):
      self.title = doc.title
    Subscription.notifyChange(self)


class TrunkRevisionModel(BaseContentModel):
  """Stores revision history associated with a trunk.

  Associated trunk is assigned parent to this model to keep them in same entity
  group.

  Attributes:

    obj_ref: Key to a doc/object stored as string.
    time_stamp: Time stamp of revision.
    commit_message: Commit message log for each instance.
  """
  obj_ref = db.StringProperty()
  commit_message = db.StringProperty()
  time_stamp = db.DateTimeProperty(auto_now=True)

  def dump_to_dict(self):
    """Returns all attributes of the object in a dictionary."""
    return {
      'obj_type': ObjectType.TRUNK_REVISION,
      'trunk_revison_parent': str(self.parent().key()),
      'trunk_revision_obj_ref': str(self.obj_ref.key()),
      'trunk_revision_commit_message': self.commit_message,
      'trunk_revision_time_stamp': self.time_stamp
      }


class RichTextModel(BaseContentModel):
  """Immutable rich text object.

  Attributes:
    data: Blob store object with rich text content.
  """
  # implicit key
  data = db.BlobProperty()

  def dump_to_dict(self):
    """Returns all attributes of the object in a dictionary."""
    return {
      'obj_type': ObjectType.RICH_TEXT,
      'rich_text_data': str(self.data)
       }

  def asText(self):
    data = self.data.decode('utf-8')
    return super(self.__class__, self).asText() + "\n" + htmlfolder.htmlfold(data)


class DocLinkModel(BaseContentModel):
  """Link to another document in the datastore.

  Stores trunk_ref, doc_ref to the document it's pointing to and also
  for the document containing the link (i.e source of the link).

  Attributes:
    trunk_ref: Reference to a trunk containing the document.
    doc_ref: Reference to a document (used to point at a specific version
      of a document).
    from_trunk_ref: Reference to the trunk containing this link.
    from_doc_ref: Reference to the doc containing this link.
    default_title: Default title for the link (useful for docs which do
      not exists yet).
  """
  trunk_ref = db.ReferenceProperty(TrunkModel)
  default_title = db.StringProperty()
  doc_ref = db.ReferenceProperty(DocModel)
  from_trunk_ref = db.ReferenceProperty(TrunkModel, collection_name='from_link')
  from_doc_ref = db.ReferenceProperty(DocModel, collection_name='from_link')

  def get_score(self, user):
    """Returns progress score for the doc.

    Looks up the DocVisitState for the score.

    Args:
     user: User whose score is fetched.
    Returns:
     Score for the doc.
    Raises:
     InvalidDocumentError: If doc is invalid.
    """
    if not self.doc_ref:
      raise InvalidDocumentError('Document referred could not be found.')
    else:
      return self.doc_ref.get_score(user)

  def ident(self):
    return str(self.doc_ref.key())

  def get_title(self):
    """Grab the up-to-date title for the document"""
    if self.trunk_ref:
      doc = db.get(self.trunk_ref.head)
      if doc and doc.title:
        return doc.title

    if self.doc_ref:
      return self.doc_ref.title

    return self.default_title


class VideoModel(BaseContentModel):
  """Stores video id and optional size configuration.

  Attributes:
    video_id: A youtube video id.
    width: Width of the embedded video.
    height: Height of the embedded video.
  """
  video_id = db.StringProperty()
  width = db.StringProperty(default='480')
  height = db.StringProperty(default='280')
  title = db.StringProperty()

  def dump_to_dict(self):
    """Returns all attributes of the object in a dictionary."""
    return {
      'obj_type': ObjectType.VIDEO,
      'video_video_id': self.video_id,
      'video_width': self.width,
      'video_height': self.height,
      'video_title': self.title
      }

  def ident(self):
    return self.video_id


# Should we replace PyShell and Quiz with one Widget model ?

class PyShellModel(BaseContentModel):
  """Link to python interpretor.

  Attributes:
    shell_url: Url to the app running python shell to be embedded as an Iframe.
  """
  shell_url = db.LinkProperty(required=True)

  def dump_to_dict(self):
    """Returns all attributes of the object in a dictionary."""
    return {
      'obj_type': ObjectType.PY_SHELL,
      'py_shell_shell_url': self.shell_url
      }


class QuizModel(BaseContentModel):
  """Link to quiz module.

  Attributes:
    quiz_url: Url to quiz app to be embedded as an Iframe.
  """
  quiz_url = db.LinkProperty(required=True)

  def dump_to_dict(self):
    """Returns all attributes of the object in a dictionary."""
    return {
      'obj_type': ObjectType.QUIZ,
      'quiz_quiz_url': self.quiz_url
      }

  def get_score(self, user):
    """Returns progress score for a quiz.

    Args:
      user: User whose score is being fetched.
    Returns:
      Score for the quiz.
    Raises:
      InvalidQuizError: If the quiz passed is not valid.
    """
    try:
      quiz_key = self.key()
    except (db.NotSavedError, AttributeError):
      raise InvalidQuizError('Quiz is not valid: it has not been saved')

    quiz_state = QuizProgressState.all().filter('user =', user).filter(
      'quiz_ref =', quiz_key).order('-time_stamp').get()

    if quiz_state:
      return quiz_state.progress_score
    else:
      return 0


class ComparableSequenceElem(object):
  """An element in a comparable sequence.

  Attributes:
    doc: Reference to the document this element represents

  When comparing two Lantern documents, each of which often is a
  sequence of links to versioned documents, we first convert them into
  a "comparable sequence" and give them to difflib to match the
  corresponding subdocument (which could be of different revision) up.
  Then the different revisions of matched subdocuments are further
  compared.

  For this to work, an element in a comparable sequence needs to say "I
  am equal" to an object with the same trunk-id even when the other object
  is of a different revision.  Also we have to inspect each element and
  be able to say which revision it is about.
  """
  def __init__(self, doc):
    # TODO(jch): There probably needs a subclass between BaseContentModel
    # and its subclasses to distinguish the ones with and the ones without
    # trunk_ref.
    self.doc = doc

  def __hash__(self):
    return id(self)

  def __eq__(self, other):
    """Are two objects 'equal' in the sense that they are of the same trunk?"""
    if self.doc.__class__ is not other.doc.__class__:
      return False
    one = getattr(self.doc, 'trunk_ref', None)
    two = getattr(other.doc, 'trunk_ref', None)
    if one and two:
      one, two = one.key(), two.key()
      return one == two
    # If neither have trunk (e.g. two videos), consider them the same
    # at the structure level, and let the content level comparison kick in.
    # If only one has trunk, they are different.
    return (not one) is (not two)


class NotePadModel(BaseContentModel):
  """An empty anchor to hook per-user notepad

  The viewer will use the combination of <object of this class, user>
  as a key to access another table, similar to annotation state, to
  display and let the user interact with the page.  The content authored
  by the course writer is empty.
  """
  def notepad(self):
    return str(self.key())

  def asText(self):
    return "NotePad"

class WidgetModel(BaseContentModel):
  """Link to widget module.

  Attributes:
    widget_url: Url to quiz app to be embedded as an Iframe.
    is_shared: True if widget is intended to be shared between different
        pages. Interactive shells will set this to be False.
  """
  widget_url = db.StringProperty(required=True)
  height = db.StringProperty()
  width = db.StringProperty()
  title = db.StringProperty()
  is_shared = db.BooleanProperty()

  @classmethod
  def _get_identifying_fields(cls, **kwargs):
    """Gets a list of fields that uniquely identify an entry.

    A Widget of the same type (e.g., Pyshell) may appear multiple times on
    the same page, perhaps with the same title. Moreover, we do not want to
    share Pyshell between different docs, since they may be focused on different
    exercises. Consequently, we need two pseudo fields to uniquely identify
    a widget:
      trunk_id: The trunk id of the hosting DocModel.
      widget_index: The nth occurrence of the widget on the page that has
          the same title. 0-based.  Caller is responsible for providing a
          unique index (when it matters).

    These pseudo fields are popped from kwargs before returning the results.
    """
    # Pop pseudo fields from kwargs
    trunk_id = kwargs.pop('trunk_id', '')
    widget_index = kwargs.pop('widget_index', 0)

    # Get base results, then append pseudo fields.
    identifying_fields = super(WidgetModel, cls)._get_identifying_fields(
        **kwargs)
    identifying_fields.append(trunk_id)
    identifying_fields.append(str(widget_index))
    return identifying_fields

  def dump_to_dict(self):
    """Returns all attributes of the object in a dictionary."""
    return {
      'obj_type': ObjectType.WIDGET,
      'widget_widget_url': self.widget_url,
      'widget_height': self.height,
      'widget_width': self.width,
      'widget_title': self.title,
      'is_shared': self.is_shared,
      }

  def get_score(self, user):
    """Returns progress score for the widget associated with given user.

    Args:
      user: User whose score is being fetched.
    Returns:
      Score for the widget.
    Raises:
      InvalidWidgetError: If the widget passed is not valid.
    """
    try:
      widget_key = self.key()
    except (db.NotSavedError, AttributeError):
      raise InvalidWidgetError('Widget is not valid: it has not been saved')

    widget_state = WidgetProgressState.all().filter('user =', user).filter(
      'widget_ref =', widget_key).order('-time_stamp').get()

    if widget_state:
      return widget_state.progress_score
    else:
      return 0


class DocVisitState(UserStateModel):
  """Maintains state of visited docs for each user.

  Attributes:
    trunk_ref: Reference to visited trunk.
    doc_ref: Reference to visited doc.
    last_visit: Time stamp for last visit to the document.
    doc_progress_score: Completion score for the visited doc.
    dirty_bit: Dirty bit is set when the scores down the trunk
      may be stale.
  """
  trunk_ref = db.ReferenceProperty(TrunkModel)
  doc_ref = db.ReferenceProperty(DocModel)
  last_visit = db.DateTimeProperty(auto_now=True)
  progress_score = db.RatingProperty(default=0)
  dirty_bit = db.BooleanProperty(default=False)


class QuizProgressState(UserStateModel):
  """Maintains per quiz progress state for each user.

  Attributes:
    quiz_ref: Reference to quiz model.
    progress_score: Completion/progress score for the quiz.
    time_stamp: Timestamp to maintain history of progress.
  """
  quiz_ref = db.ReferenceProperty(QuizModel)
  progress_score = db.RatingProperty(default=0)
  time_stamp = db.DateTimeProperty(auto_now=True)


class WidgetProgressState(UserStateModel):
  """Maintains per widget progress state for each user.

  Attributes:
    widget_ref: Reference to quiz model.
    progress_score: Completion/progress score for the quiz.
    time_stamp: Timestamp to maintain history of progress.
    user_data: Opaque user data stored as a BlobProperty. This is per-user
        state to be persisted on behalf of the widget.
  """
  widget_ref = db.ReferenceProperty(WidgetModel)
  progress_score = db.RatingProperty(default=0)
  time_stamp = db.DateTimeProperty(auto_now=True)
  user_data = db.BlobProperty()


class AnnotationState(UserStateModel):
  """Maintains per user annotation for each annotated object.

  Attributes:
    object_ref: Reference to annotated object.
    trunk_ref:  Reference to annotated trunk.
    doc_ref: Reference to annotated doc.
    annotation_data: Dictionary representing annotation data pickled
      and kept in text form.
    last_modified: Time for last modification.
  """
  object_ref = db.ReferenceProperty(reference_class=None)
  trunk_ref = db.ReferenceProperty(TrunkModel, collection_name='annotation')
  doc_ref = db.ReferenceProperty(DocModel, collection_name='annotation')
  last_modified = db.DateTimeProperty(auto_now=True)
  annotation_data = db.BlobProperty()


class NotePadState(UserStateModel):
  """Per user note embedded in the document.

  Attributes:
    object_ref: Reference to the NotePad object.
    notepad_data: User generated rich-text data.
  """
  object_ref = db.ReferenceProperty(reference_class=NotePadModel)
  notepad_data = db.TextProperty()


class RecentCourseState(UserStateModel):
  """Maintains list of recent courses accessed by user.

  Useful in building homepage.

  Attributes:
    time_stamp = Time of last visit.
    course_trunk_ref = Trunk id of the course.
    course_doc_ref = Doc_id of the course.
    course_score = Course progress state.
    last_visited_doc_ref = Doc last visited for the course.
  """
  time_stamp = db.DateTimeProperty(auto_now=True)
  course_trunk_ref = db.ReferenceProperty(TrunkModel)
  course_doc_ref = db.ReferenceProperty(DocModel)
  course_score = db.RatingProperty()
  last_visited_doc_ref = db.ReferenceProperty(
      DocModel, collection_name='recent_course_state')


class TraversalPath(UserStateModel):
  """Maintains path that user traversed to reach the document.
  Sequential list of doc_ids, referring to the path down the
  tree followed to reach the current doc.

  NOTE(mukundjha): We no longer are required to store trunk ids,
  because all the docs in the path are added based on the history.

  Attributes:
    current_doc: Id for the document for which path is stored.
    path: Ordered list of doc_ids.
  """
  current_doc = db.ReferenceProperty(DocModel)
  current_trunk = db.ReferenceProperty(TrunkModel)
  path = db.ListProperty(db.Key)


class VideoState(UserStateModel):
  """Stores the paused state for a video for a particular user.

  Attributes:
    video_ref : Id for the video object
    paused_time: Float value for seconds.
  """
  video_ref = db.ReferenceProperty(VideoModel)
  paused_time = db.FloatProperty(default=0)


class Classroom(UserStateModel):
  """Defines a classroom to be managed by the current user (teacher).

  Links to list of students (enrollment).  Should be able to get the enrollment
  list using:

    enrolled_students = classroom.enrollment_set.get()

  Class Attributes:
    DEFAULT_MAX_ENROLLMENT: Default maximum for number of students (100).

  Attributes:
    user: The teacher that manages the classroom.
    name: Name for the classroom, e.g., year, quarter, period, etc. to be
        defined by the teacher.
    start_date: Effective start date of the class.
    course_trunk_ref: Reference to the trunk of the course.
    course_doc_ref: Reference to the doc model the course.
    max_enrollment: Maximum number of students for the class. Defaults to 100.
    class_score: Keeps track of overall progress for the class.
  """
  DEFAULT_MAX_ENROLLMENT = 100

  name = db.StringProperty(required=True)
  start_date = db.DateTimeProperty(required=True)
  course_trunk_ref = db.ReferenceProperty(TrunkModel, required=True)
  course_doc_ref = db.ReferenceProperty(DocModel, required=True)
  max_enrollment = db.IntegerProperty(default=DEFAULT_MAX_ENROLLMENT)
  class_score = db.RatingProperty()


class Enrollment(db.Model):
  """An enrollment entry for a Classroom.

  Attributes:
    classroom: The classroom for which this enrollment belongs.
    email: Email of the student that should receive an invitation to join the
        class.
    account_key: The key name of the Account
    is_invited: False until invitation is sent.
    is_enrolled: False until the student accepts the invitation.
    student: Set to the student's UserProperty when accepting the invitation.
        Should be None before enrollment.
  """
  classroom = db.ReferenceProperty(Classroom, required=True)
  email = db.StringProperty(required=True)
  account_key = db.StringProperty()
  is_invited = db.BooleanProperty()
  is_enrolled = db.BooleanProperty()
  student = db.UserProperty()


class Subscription(db.Model):
  """Maps trunks to people who subscribed for the changes.

  Attributes:
    trunk: the trunk
    user: the user who subscribed for the page
    recursive: the subscription covers all the subpages
    method: how should the user be notified; possible values
            TBD, including (immediate, onceaday, meh)
  """
  # Preferred notification methods
  METH_IMMEDIATE = 'immediate'  # one mail per one detection of change
  METH_ONCEADAY = 'onceaday'    # aggregated into one message per day
  METH_MEH = 'meh'              # do not bother me

  METH_DEFAULT = METH_ONCEADAY

  # Changes to the same trunk within this number of seconds
  # are collapsed into a single notification.
  ASYNC_SLOP_SEC = 120

  # DateTime format used for logging
  DATETIME_STRING_FORMAT = "%Y-%m-%d %H:%M:%S (%Z)"

  trunk = db.ReferenceProperty(TrunkModel, required=True)
  user = db.UserProperty(auto_current_user_add=True, required=True)
  recursive = db.BooleanProperty(default=False, required=True)
  method = db.StringProperty(default=METH_DEFAULT, required=True)

  @classmethod
  def notifyChange(cls, trunk):
    """The Web interface notifies that trunk-tip has changed

    Do minimum here and have asynchronous process to take care
    of the most of the notification task.
    """
    now = datetime.datetime.utcnow()
    logging.info("Notifying change at %s to %s." % (
        now.strftime(cls.DATETIME_STRING_FORMAT),
        trunk.title))
    ago = now - datetime.timedelta(seconds=cls.ASYNC_SLOP_SEC)
    query = (SubscriptionNotification.all().filter('trunk =', trunk).
             filter('timestamp >', ago))
    if 0 < query.count(1):
      logging.info("Notification for the same trunk exists (%d)." % query.count())
      for e in query:
        logging.info("Other was made at %s" %
                     e.timestamp.strftime(cls.DATETIME_STRING_FORMAT))
      return
    note = SubscriptionNotification(trunk=trunk)
    note.put()


class SubscriptionNotification(db.Model):
  """List of trunk changes

  Whenever the tip of the trunk changes, a record of this type is
  inserted to the database.  This is matched against Subscription
  and ChangesSeen (see below) to determine the users that need to
  be notified.
  """
  trunk = db.ReferenceProperty(TrunkModel, required=True)
  timestamp = db.DateTimeProperty(auto_now=True, required=True)


class ChangesSeen(db.Model):
  """Records what document was seen at the tip of trunk by the user.

  For each user who subscribes to changes to a trunk, this keeps track
  of the last version of the trunk and the time of that observation (i.e.
  the time a change notification was sent out to the user).  Together
  with SubscriptionNotification (see above), the system can tell what
  changes to which trunks are still not notified to what user.  When a
  notification is sent out to the user, the corresponding record is
  updated.

  Attributes:
    trunk: the trunk
    user: the user who observed the trunk
    doc: the DocModel that was at the tip of the trunk
    timestamp: the time the observation was last made
  """
  trunk = db.ReferenceProperty(TrunkModel, required=True)
  user = db.UserProperty(auto_current_user_add=True, required=True)
  doc = db.ReferenceProperty(DocModel, required=True)
  timestamp = db.DateTimeProperty(required=True)
