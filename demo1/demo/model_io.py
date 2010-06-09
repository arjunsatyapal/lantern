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

"""Utility for importing and exporting models."""

# Python imports
import base64
import datetime
import logging

# AppEngine imports
from google.appengine.ext import db
from google.appengine.api import users

# Local imports
from demo import models

# Transcoder mode
CSV = 0
YAML = 1


def FieldCsvEncode(fn):
  """Encodes the field value using the specified function.

  If None, returns default value.
  """
  def _Convert(value):
    if value is None:
      return ""
    return fn(value)

  return _Convert


def FieldEncode(fn):
  """Encodes the field value using the specified function.

  If None, returns default value.
  """
  def _Convert(value):
    if value is None:
      return None
    return fn(value)

  return _Convert


def Utf8Decode(value):
  return value.decode('utf-8')


def UserEncode(user):
  """Returns User encoded as string: <user_id>|<email>.

  NOTE(vchen): Using '|' as the separator for import/export should be
  acceptable, because it is not expected to be a part of an email address.
  """
  if not user:
    return ''
  assert isinstance(user, users.User)
  return "%s|%s" % (user.user_id(), user.email())


def UserDecode(user_str):
  """Returns User with string encoding of: <user_id>|<email>.

  Note that the encoding must match that of UserEncode()
  """
  try:
    user_id, email = user_str.split('|', 1)
  except ValueError:  # only 1 part given
    return users.User(email=user_str)
  return users.User(email=email, _user_id=user_id)


def BinaryEncode(value):
  """If None, returns empty string. Otherwise, encode to a string."""
  if value is None:
    return ""
  return base64.b64encode(value)


def BinaryDecode(value_str):
  """Decodes string to return a binary value."""
  return base64.b64decode(value_str)


def DatetimeEncode(value):
  """Encodes datetime to a string, UTC."""
  return datetime.datetime.strftime(value, '%Y-%m-%d %H:%M')


def DatetimeDecode(value):
  """Decodes datetime from a string, UTC."""
  return datetime.datetime.strptime(value, '%Y-%m-%d %H:%M')


def OptionalFieldDecode(fn):
  """Wraps the conversion function to convert empty string to None.

  Use for loading optional fields to preserve None.
  """

  def _Convert(str_value):
    if str_value == '':
      return None
    return fn(str_value)

  return _Convert


def ListCsvEncode(fn):
  """Encodes the list value as a CSV, applying the function to each element."""

  def _Convert(list_value):
    return ','.join(("'" + fn(elem) + "'") for elem in list_value)

  return _Convert


def ListCsvDecode(fn):

  def _RemoveQuotes(value):
    if value.startswith("'") and value.endswith("'"):
      return value[1:-1]
    return value

  def _Convert(csv_value):
    return [fn(_RemoveQuotes(elem)) for elem in csv_value.split(',')
            if _RemoveQuotes(elem)]

  return _Convert


def ListEncode(fn):
  """Encodes the list value, applying the function to each element."""

  def _Convert(list_value):
    return [fn(elem) for elem in list_value]

  return _Convert


def ListDecode(fn):

  def _Convert(list_value):
    return [fn(elem) for elem in list_value]

  return _Convert



class Transcoder(object):
  """Abstract base class for encoding and decoding a property of a model.

  It is expected that a subclass exists for each Model.

  Attributes:
    mode: CSV or YAML specifies how to encode and decode each property.

  Derived classes should set the following attributes in the constructor.

    _exported_properties: Ordered list of property names to export/import
    _encoding_map: Map of property name to (fn, default_value) tuple where
        'fn' is an encoding function that takes a single argument.
    _decoding_map: Map of property name to a decoding function that takes
        a single argument.
  """

  def __init__(self, mode):
    """Constructs transcoder for the specified mode."""
    self.mode = mode

    if mode == CSV:
      self._ListEncode = ListCsvEncode
      self._ListDecode = ListCsvDecode
      self._FieldEncode = FieldCsvEncode
    else:
      self._ListEncode = ListEncode
      self._ListDecode = ListDecode
      self._FieldEncode = FieldEncode

    self._exported_properties = []
    self._encoding_map = {}
    self._decoding_map = {}

  def GetExportedProperties(self):
    """Returns list of property names for that should be encoded/decoded.

    The fields will be encoded and decoded in the specified order.
    """
    return self._exported_properties

  def GetEncodingMap(self):
    return self._encoding_map

  def GetDecodingMap(self):
    return self._decoding_map

  def EncodeProperty(self, property, value):
    """Encodes the specified property value and returns it."""
    fn_default_tuple = self._encoding_map.get(property)
    if not fn_default_tuple:
      return ''
    convert_fn, default_val = fn_default_tuple
    if value is None:
      if default_val is None:
        return ''
      else:
        return default_val
    return convert_fn(value)

  def DecodeProperty(self, property, value):
    """Decodes the specified property value and returns it."""
    convert_fn = self._decoding_map.get(property)
    if not convert_fn or value is None:
      return None
    return convert_fn(value)


class AccountXcoder(Transcoder):
  """Encoder and Decoder for Account instances."""

  def __init__(self, mode):
    super(AccountXcoder, self).__init__(mode)

    # Ordered list of fields to export/import by default (for bulkloading)
    self._exported_properties = (
        '__key__',
        'user',
        'user_id',
        'email',
        'nickname',
        'created',
        'modified',
        'stars',
        'fresh',
        'lower_email',
        'lower_nickname',
        'xsrf_secret',
        )

    # Field-encoding map for Account for use when exporting.
    # Maps property name to (fn, default_value) tuple where 'fn' is an encoding
    # function.
    self._encoding_map = {
        '__key__': (str, None),
        'user': (UserEncode, None),
        'user_id': (str, None),
        'email': (str, None),
        'nickname': (str, None),
        'created': (DatetimeEncode, None),
        'modified': (DatetimeEncode, None),
        'stars': (self._ListEncode(str), ''),
        'fresh': (bool, ''),
        'lower_email': (str, ''),
        'lower_nickname': (str, ''),
        'xsrf_secret': (BinaryEncode, ''),
        }

    # Field-decoding map for Account for use when importing.
    # Maps property name to a decoding function.
    self._decoding_map = {
        '__key__': lambda x: db.Key(encoded=x),
        'user': UserDecode,
        'user_id': str,
        'email': str,
        'nickname': Utf8Decode,
        'created': DatetimeDecode,
        'modified': DatetimeDecode,
        'stars': self._ListDecode(str),
        'fresh': OptionalFieldDecode(bool),
        'lower_email': OptionalFieldDecode(str),
        'lower_nickname': OptionalFieldDecode(str),
        'xsrf_secret': BinaryDecode,
        }


class PedagogyXcoder(Transcoder):
  """Encoder and Decoder for PedagogyModel instances."""

  def __init__(self, mode):
    super(PedagogyXcoder, self).__init__(mode)

    # Ordered list of fields to export/import by default (for bulkloading)
    self._exported_properties = (
      '__key__',
      'title',
      'creator',
      'created',
      'modified',
      'description',
      'authors',
      'ddc',
      'labels',
      'language',
      'grade_level',
      'rating',
      'revision',
      'is_published',
      'template_reference',
      )

    # Field-encoding map for PedagogyModel for use when exporting.
    # Maps property name to (fn, default_value) tuple where 'fn' is an encoding
    # function.
    self._encoding_map = {
        '__key__': (str, None),
        'title': (str, None),
        'creator': (UserEncode, None),
        'created': (DatetimeEncode, None),
        'modified': (DatetimeEncode, None),
        'description': (self._FieldEncode(str), ''),
        'authors': (self._ListEncode(UserEncode), ''),
        'ddc': (self._FieldEncode(str), ''),
        'labels': (self._ListEncode(str), ''),
        'language': (self._FieldEncode(str), ''),
        'grade_level': (self._FieldEncode(int), ''),
        'rating': (self._FieldEncode(int), ''),
        'revision': (self._FieldEncode(int), 0),
        'is_published': (self._FieldEncode(bool), False),
        'template_reference': (self._FieldEncode(str), ''),
        }

    # Field-decoding map for PedagogyModel for use when importing.
    # Maps property name to a decoding function.
    self._decoding_map = {
        '__key__': lambda x: db.Key(encoded=x),
        'title': Utf8Decode,
        'creator': UserDecode,
        'created': DatetimeDecode,
        'modified': DatetimeDecode,
        'description': OptionalFieldDecode(Utf8Decode),
        'authors': self._ListDecode(UserDecode),
        'ddc': OptionalFieldDecode(str),
        'labels': self._ListDecode(db.Category),
        'language': OptionalFieldDecode(str),
        'grade_level': OptionalFieldDecode(int),
        'rating': OptionalFieldDecode(lambda x: db.Rating(x)),
        'revision': OptionalFieldDecode(int),
        'is_published': OptionalFieldDecode(bool),
        'template_reference': OptionalFieldDecode(lambda x: db.Key(encoded=x)),
        }
