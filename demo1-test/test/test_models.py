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

"""Tests for the Lantern data models."""

# Python imports
import logging
import unittest

# AppEngine imports
from google.appengine.ext import db
from google.appengine.api import users

# local imports
from demo import models

class ModelsHashTest(unittest.TestCase):
  """Tests the underlying hashing used to create keys for referenced content.
  """

  def testBaseGetFields(self):
    fields1 = models.BaseContentModel._get_identifying_fields(
        title='Title', widget_url='http://khanacademy.org/?trig')

    # BaseContentModel has no title, so does not contribute to fields used
    # to compute the hash.
    fields2 = models.BaseContentModel._get_identifying_fields(
        title='Title2', widget_url='http://khanacademy.org/?trig')

    self.assertEquals(fields1, fields2)

  def testWidgetModelFieldsWithoutIndex(self):
    fields1 = models.WidgetModel._get_identifying_fields(
        title='Title', widget_url='http://khanacademy.org/?trig')

    fields2 = models.WidgetModel._get_identifying_fields(
        title='Title', widget_url='http://khanacademy.org/?trig')

    self.assertEquals(fields1, fields2)

  def testWidgetModelFieldsWithIndex(self):
    fields1 = models.WidgetModel._get_identifying_fields(
        title='Title', widget_url='http://khanacademy.org/?trig',
        widget_index=0)

    fields2 = models.WidgetModel._get_identifying_fields(
        title='Title', widget_url='http://khanacademy.org/?trig',
        widget_index=1)

    self.assertNotEquals(fields1, fields2)

  def testInsertWidgetModelWithIndex(self):
    obj = models.WidgetModel.insert(
        title='Title', widget_url='http://khanacademy.org/?trig',
        is_shared=True, widget_index=0)

    self.assertTrue(obj.is_shared)


if __name__ == "__main__":
  unittest.main()
