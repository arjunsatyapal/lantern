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
import logging
import md5
import operator
import os
import re
import time

# AppEngine imports
from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import users


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

### Pedagogy ###


class PedagogyModel(db.Model):
  """Base class of items in a pedagogy hierarchy.

  The hieracrchy consists of the levels:
    - Curriculum
    - Course
    - Lesson
    - Module
    - Content and Exercise

  The meta information at each layer of the hierarchy are essentially the
  same, e.g., authorship, dates, labels, rating, etc.

  Each entry is expected to be stored with a randomly generate key name,
  although there may be some structure to the keyname to hint at the layer of
  the hierarchy.

  Do not instantiate this class directly; use one of its derived classes.

  Attributes:
    title: The title of the item.
    creator: The user that created the item.
    created: The timestamp when the item was created.
    modified: The timestamp when the item was last modified.
    authors: An optional list of additional authors.
    ddc: Optional Dewey Decimal Classification, using ID of one of the
        "divisions".
    labels: Optional list of tags.
    language: Language in which the content is written.
    grade_level: Optional indication of grade level of the item.
    rating: Optional rating for the item.

    revision: Revision number of the entry.
        TODO(vchen): How to autoincrement? It should really be
        CounterProperty().
        Where do old revisions go?
    is_published: Whether this is published to the world.

    template_reference: References another instance that represents a template
        from which to "inherit" content. Optional.

    _kname: Temporary holder of key name before it is stored.
    _refs: Temporary storage of references before persisting

  TODO(vchen): Are there permissions, acls?
  TODO(vchen): Determine how to handle revision history!
  """

  title = db.StringProperty(required=True)
  creator = db.UserProperty(auto_current_user_add=True, required=True)
  created = db.DateTimeProperty(auto_now_add=True)
  modified = db.DateTimeProperty(auto_now=True)
  description = db.TextProperty();
  authors = db.ListProperty(users.User)  # Multiple authors allowed
  ddc = db.StringProperty(verbose_name='Dewey Decimal')
  labels = db.ListProperty(db.Category)
  language = db.StringProperty()
  grade_level = db.IntegerProperty()
  rating = db.RatingProperty()
  revision = db.IntegerProperty(default=0)
  is_published = db.BooleanProperty(default=False)

  template_reference = db.SelfReferenceProperty()

  # Separator to use between parts of the key.
  _KEY_SEPARTOR = ':'

  def __init__(self, *args, **kwargs):
    super(PedagogyModel, self).__init__(*args, **kwargs)
    self._kname = None
    self._refs = []

  @classmethod
  def gen_random_string(cls, num_chars):
    """Generates a random string of the specified number of characters."""
    # Uses base64 encoding, which has roughly 4/3 size of underlying data.
    remainder = num_chars % 4
    num_bytes = ((num_chars + remainder) / 4) * 3
    random = os.urandom(num_bytes)
    random_str = base64.b64encode(random)
    return random_str[:num_chars]

  @classmethod
  def insert_with_random_key(cls, key_prefix, num_random_chars, **kwargs):
    """Generates a random key, making sure it's not in the current database.

    Args:
      key_prefix: If not empty or None, it is prepended to the randomly
        generated key string.
      num_random_chars: Number of random characters to generate for the key.
      kwargs: The initial values for the required fields, passed to
        get_or_insert()

    Returns:
      The newly inserted object.
    """
    while True:
      key_name = cls.gen_random_string(num_random_chars)
      if key_prefix:
        key_name = "".join((key_prefix, cls._KEY_SEPARTOR, key_name))

      record = cls.get_or_insert(key_name, **kwargs)
      # Validate
      is_valid = True
      for field, value in kwargs.iteritems():
        if value != getattr(record, field, None):
          is_valid = False
          break
      if is_valid:
        break
    return record

  # Instance methods

  def get_references(self, content_ref_class):
    """Gets the reference objects that have this item as a parent.

    This is a utility function that returns the references to the associated
    "content".  If there is a template reference, the returned list merges
    the template's list.  Direct references override the template ones at the
    same ordinal locations.  When an override reference is None, it implies
    erasure.

    For example:
    - A Course is associated with references to all its Lessons.
    - A Lesson is assoicated with references to all its Modules.

    Args:
      content_ref_class: A derived class of PedagogyRef model that represents
         a reference to content.

    Returns:
      A list of references (instances of content_ref_class class), sorted by
      ordinal.
    """
    if not self.is_saved():
      return self._refs
    base_content_refs = []
    if self.template_reference:
      base_content_refs = self.template_reference.get_references(
          content_ref_class)

    content_refs = content_ref_class.all().ancestor(self).order('ordinal')
    if not base_content_refs:
      return [r for r in content_refs]
    if content_refs.count() == 0:
      return base_content_refs

    # Need to merge
    ordinal_map = dict([
        (ref.ordinal, idx) for idx, ref in enumerate(base_content_refs)])
    needs_sort = False
    delete_indexes = []
    for ref in content_refs:
      idx = ordinal_map.get(ref.ordinal)
      if idx is None:
        if ref.reference:
          base_content_refs.append(ref)
          needs_sort = True
      else:
        if ref.reference:
          base_content_refs[idx] = ref
        else:
          delete_indexes.append(idx)

    # Delete any
    if delete_indexes:
      for idx in reversed(delete_indexes):
        del base_content_refs[idx]
    if needs_sort:
      return sorted(base_content_refs, key=lambda x: x.ordinal)
    else:
      return base_content_refs


class PedagogyRef(db.Model):
  """An abstract reference model that binds two layers of the pedagogy together.

  For example
    - A Course has an ordered list of references to Lessons.
    - A Lesson has an ordered list of references to Modules.

  A set of references that share the same parent should have unique ordinal
  numbers.
    - The parent represents a container.
    - The set of references represents the contents of the container.

  Derived classes are expected to define a 'reference' property of type
  ReferenceProperty that references the "content" model.

  Each instance of a reference is expected to be created with a parent.

  Attributes:
    reference: To be defined by derived class.
    ordinal: A numeric value that controls the ordering of content and
        the override locations.
    section_label: A displayed label to associate with this reference. If
        unspecified, it will be the 1-based index of the item within the
        collection.

    _reference: Convenient object reference before the storing into the
      database, because the actual reference key may not exist yet. When
      bulk-loading, this provides a way to bind the objects together before
      storing.
  """

  reference = None  # To be overridden by derived classes
  ordinal = db.IntegerProperty(required=True)
  section_label = db.StringProperty()

  def __init__(self, *args, **kwargs):
    super(PedagogyRef, self).__init__(*args, **kwargs)
    self._ref = None

  def get_reference(self):
    """Convenience method to return one of the reference objects.

    If the actual datastore reference is not None, it is returned. Otherwise,
    returns the object reference.
    """
    if self.is_saved():
      return self.reference
    return self._ref


# Concrete Pedagogy classes

class ModuleContent(PedagogyModel):
  """A pointer to the educational content for a Module.

  A module should be a small unit of instruction consisting of educational
  content and a set of exercises. It is expected that most modules would have
  a reference to a single URI for the content.

  The actual content referenced by this item could be complex, further
  embedding multi-media presentations.

  Attributes:
    uri: This is intended to point to content that can be embedded within the
        the application.  The URI could refer to static content provided by the
        app, data from a git repository, external web content, etc.
        Since StringProperty has a limit of 500 characters, uri uses a
        TextProperty....can't be indexed.

  TODO(vchen): Probably need to support different types/styles of content,
  unless it's always IFRAME....The content type may itself be multi-part,
  "rich" content that includes template of how to lay out its content?
  """

  uri = db.LinkProperty(required=True)


class ModuleExercise(PedagogyModel):
  """A pointer to an exercise for a Module.

  TODO(vchen): Determine how to model an exercise.  There needs to be type
  of exercise, problem statement, content, answers, evaluator for the answer,
  etc.
  """

  difficulty = db.RatingProperty(default=10)


class LessonModule(PedagogyModel):
  """A Module consists of educational content and a set of exercises.
  """

  def get_content_refs(self):
    return self.get_references(ContentRef)

  def get_exercise_refs(self):
    return self.get_references(ExerciseRef)


class CourseLesson(PedagogyModel):
  """A Lesson consists of an ordered list of Modules.
  """

  def get_modules(self):
    return self.get_references(ModuleRef)


class Course(PedagogyModel):
  """A Course consists of an ordered list of Lessons.
  """

  def get_lessons(self):
    return self.get_references(LessonRef)


class ContentRef(PedagogyRef):
  """A ContentRef has a LessonModule as its parent.

  This class represents a Module's reference to content. An ordered collection
  of these may be associated with each Module. The ordinal numbers for each
  member of the collection should be unique and defines the sort order.
  """

  reference = db.ReferenceProperty(ModuleContent)


class ExerciseRef(PedagogyRef):
  """A ExerciseRef has a LessonModule as its parent.

  This class represents a Module's reference to an exercise. An ordered
  collection of these may be associated with each Module. The ordinal numbers
  for each member of the collection should be unique and defines the sort
  order.
  """

  reference = db.ReferenceProperty(ModuleExercise)


class ModuleRef(PedagogyRef):
  """A ModuleRef has a CourseLesson as its parent.

  This class represents a Lesson's reference to a Module. An ordered
  collection of these may be associated with each Lesson. The ordinal numbers
  for each member of the collection should be unique and defines the sort
  order.
  """

  reference = db.ReferenceProperty(LessonModule)


class LessonRef(PedagogyRef):
  """A LessonRef has a Course as its parent.

  This class represents a Course's reference to a Lesson. An ordered
  collection of these may be associated with each Course. The ordinal numbers
  for each member of the collection should be unique and defines the sort
  order.
  """

  reference = db.ReferenceProperty(CourseLesson)

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

### New Models ## 


class DocModel(db.Model):
  """ Stores various attributes associated with a document.
 
  TODO(mukundjha) : adopt/merge PedagogyModel 
  """

  docId = db.StringProperty()


class StudentState (db.Model):
  """ Maintains minimal student state.
 
  TODO(mukundjha) : expand the model and use proper references
  """
  #student = db.ReferenceProperty(Account)
  student = db.UserProperty()
  #doc = db.ReferenceProperty(DocModel)
  doc = db.StringProperty()
  status = db.RatingProperty()
