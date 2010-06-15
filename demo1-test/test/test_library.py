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

"""Tests for the Lantern library functions."""

# Python imports
import logging
import unittest
import os
# AppEngine imports
from google.appengine.ext import db
from google.appengine.api import users

# local imports
from demo import library
import settings

ROOT_PATH = settings.ROOT_PATH
_INVALID_FILE_PATH = os.path.join(ROOT_PATH, "non-existent-file");
_INVALID_YAML_FILE = os.path.join(ROOT_PATH, "invalid-yaml-file");
_INVALID_NODE_FILE = os.path.join(ROOT_PATH, "valid-leaf-file");
_INVALID_LEAF_FILE = os.path.join(ROOT_PATH, "valid-node-file");
_VALID_NODE_FILE = os.path.join(ROOT_PATH, "valid-node-file");
_VALID_LEAF_FILE = os.path.join(ROOT_PATH, "valid-leaf-file");


class ParseYamlTest(unittest.TestCase):
  """Tests for parse_yaml function."""

  def testLoadInvalidFilePath(self):
    data_dict = library.parse_yaml(_INVALID_FILE_PATH)
    self.assertEquals(1, len(data_dict))
    self.assertTrue('errorMsg' in data_dict)

  def testLoadInvalidFile(self):
    data_dict = library.parse_yaml(_INVALID_YAML_FILE)
    self.assertEquals(1, len(data_dict))
    self.assertTrue('errorMsg' in data_dict)

  def testLoadValidFile(self):
    data_dict = library.parse_yaml(_VALID_NODE_FILE)
    self.assertFalse('errorMsg' in data_dict)
    self.assertEquals(9, len(data_dict))
    self.assertEquals("group", data_dict.get('doc_type'))
    self.assertEquals("Course", data_dict.get('doc_type_desc'))
    self.assertEquals("DUdpMQXAZewtzPdkLtwW6K", data_dict.get('doc_key'))
    self.assertEquals("AP CS Python", data_dict.get('doc_title'))
    self.assertEquals("2010-05-27 10:15", data_dict.get('doc_created_on'))
    self.assertEquals("mukundjha@google.com", data_dict.get('doc_creator'))
    self.assertEquals(['p1', 'p2', 'p3'], data_dict.get('doc_parents'))
    self.assertEquals(2, len(data_dict.get('doc_content')))
    self.assertEquals("AlRG3wQOBqMc2nIwjoHZZ8", 
    data_dict.get('doc_content')[0]['key'])

    self.assertEquals("Overview of AP CS Learning with Python", 
    data_dict.get('doc_content')[0]['title'])

    self.assertEquals("g", data_dict.get('doc_content')[0]['type'])
    self.assertEquals("BQYVV1KayQ2xjccQgIXfP+", 
    data_dict.get('doc_content')[1]['key'])

    self.assertEquals("The way of the program", 
    data_dict.get('doc_content')[1]['title'])

    self.assertEquals("g", data_dict.get('doc_content')[1]['type'])


class ParseNodeTest(unittest.TestCase):
  """Tests for parse node function."""

  def testLoadInvaildNodePath(self):
    data_dict = library.parse_node(_INVALID_FILE_PATH)
    self.assertEquals(1, len(data_dict))
    self.assertTrue('errorMsg' in data_dict)
 
  def testLoadInvaildFilePath(self):
    data_dict = library.parse_node(_VALID_LEAF_FILE)
    self.assertEquals(1, len(data_dict))
    self.assertTrue('errorMsg' in data_dict)
 
  def testLoadValidFile(self):
    data_dict = library.parse_node(_VALID_NODE_FILE)
    self.assertFalse('errorMsg' in data_dict)
    self.assertEquals(9, len(data_dict))
    self.assertEquals("group", data_dict.get('doc_type'))
    self.assertEquals("Course", data_dict.get('doc_type_desc'))
    self.assertEquals("DUdpMQXAZewtzPdkLtwW6K", data_dict.get('doc_key'))
    self.assertEquals("AP CS Python", data_dict.get('doc_title'))
    #self.assertEquals("AP AP course on Python", data_dict.get('doc_desc'))
    self.assertEquals("2010-05-27 10:15", data_dict.get('doc_created_on'))
    self.assertEquals("mukundjha@google.com", data_dict.get('doc_creator'))
    self.assertEquals(['p1', 'p2', 'p3'], data_dict.get('doc_parents'))
    self.assertEquals(2, len(data_dict.get('doc_content')))

    self.assertEquals("AlRG3wQOBqMc2nIwjoHZZ8", 
    data_dict.get('doc_content')[0]['key'])

    self.assertEquals("Overview of AP CS Learning with Python",
    data_dict.get('doc_content')[0]['title'])

    self.assertEquals("g", data_dict.get('doc_content')[0]['type'])
    self.assertEquals("BQYVV1KayQ2xjccQgIXfP+", 
    data_dict.get('doc_content')[1]['key'])
    self.assertEquals("The way of the program", 
    data_dict.get('doc_content')[1]['title'])

    self.assertEquals("g", data_dict.get('doc_content')[1]['type'])


class ParseLeafTest(unittest.TestCase):
  """Tests for parse_leaf function."""

  def testLoadInvaildLeafPath(self):
    data_dict = library.parse_leaf(_INVALID_FILE_PATH)
    self.assertEquals(1, len(data_dict))
    self.assertTrue('errorMsg' in data_dict)

  def testLoadInvaildFilePath(self):
    data_dict = library.parse_leaf(_VALID_NODE_FILE)
    self.assertEquals(1, len(data_dict))
    self.assertTrue('errorMsg' in data_dict)

  def testLoadValidFile(self):
    data_dict = library.parse_leaf(_VALID_LEAF_FILE)
    self.assertFalse('errorMsg' in data_dict)
    self.assertEquals(9, len(data_dict))
    self.assertEquals("content", data_dict.get('doc_type'))
    self.assertEquals("module", data_dict.get('doc_type_desc'))
    self.assertEquals("CE9+naE8SU6kMS05xno8Qg", data_dict.get('doc_key'))
    self.assertEquals("Values and types", data_dict.get('doc_title'))
    #self.assertEquals("AP AP course on Python", data_dict.get('doc_desc'))
    self.assertEquals("2010-05-27 10:15", data_dict.get('doc_created_on'))
    self.assertEquals("mukundjha@google.com", data_dict.get('doc_creator'))
    self.assertEquals(['p1', 'p2', 'p3'], data_dict.get('doc_parents'))
    self.assertEquals("This is a message", data_dict.get('doc_content'))


if __name__ == "__main__":
  unittest.main()
