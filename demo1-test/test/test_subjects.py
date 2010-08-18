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
import StringIO
import unittest
from django.utils import simplejson

# Local imports
from common import subjects

_TEST_YAML = """
root:
 - math
 - technology
 - communication
 - health
 - money
 - society
 - 'sports & recreation'
 - 'hobby'
 - 'misc'

technology:
 - physics
 - chemistry
 - biology
 - geology
 - medicine
 - engineering

engineering:
 - mechanical
 - electrical
 - chemical
 - aeronautical
 - genetic
 - 'software/computation'
 - food
 - textiles
 - education

'software/computation':
 - 'introduction to computer programming'
 - 'algorithms & data structures'
 - 'abstraction'
 - 'programming languages'
 - 'operating systems'
 - 'compilers'
 - 'memory architectures and coping with latency'
 - 'data communication, networks and routing'

'programming languages':
 - C
 - BASIC
 - C++
 - 'ECMAScript derivatives'
 - FORTRAN
 - Haskell
 - Python
"""


class SubjectTaxonomyTest(unittest.TestCase):
  """Tests the SubjectTaxonomy class."""

  def testSimpleRoots(self):
    taxonomy = subjects.SubjectTaxonomy()
    rootIds = [
        'math',
        'technology',
        'health',
        ]
    for rootId in rootIds:
      item = subjects.SubjectItem(rootId)
      taxonomy.AddSubject(item, None)

    self.assertEqual(3, len(taxonomy._roots))
    self.assertEqual('technology',
                     taxonomy.GetSubject('technology').subject_id)

  def testYamlImport(self):
    stream = StringIO.StringIO(_TEST_YAML)
    taxonomy = subjects._GetSubjectsTaxonomyFromYaml(stream)

    self.assertEqual(9, len(taxonomy._roots))
    self.assertEqual('technology',
                      taxonomy.GetSubject('technology').subject_id)
    self.assertEqual(6, len(taxonomy.GetChildSubjects('technology')))

    self.assertEqual('programming languages',
                     taxonomy.GetParent('Python').subject_id)

  def testRootToDictOfRoot(self):
    stream = StringIO.StringIO(_TEST_YAML)
    taxonomy = subjects._GetSubjectsTaxonomyFromYaml(stream)

    result = subjects._ToDict(taxonomy, None, 1)
    self.assertTrue(isinstance(result, dict))
    self.assertEqual(1, len(result))
    self.assertEqual(9, len(result['root']))

    item = result['root'][7]
    self.assertEqual('hobby', item['i'])
    self.assertEqual(True, item['l'])

  def testRootToDict(self):
    stream = StringIO.StringIO(_TEST_YAML)
    taxonomy = subjects._GetSubjectsTaxonomyFromYaml(stream)

    result = subjects._ToDict(taxonomy, None, 2)
    self.assertTrue(isinstance(result, dict))
    self.assertEqual(2, len(result))
    self.assertEqual(9, len(result['root']))
    self.assertEqual(6, len(result['technology']))

    item = result['technology'][5]
    self.assertEqual('engineering', item['i'])
    self.assertEqual(False, item['l'])

  def testEngineeringToDict(self):
    stream = StringIO.StringIO(_TEST_YAML)
    taxonomy = subjects._GetSubjectsTaxonomyFromYaml(stream)

    result = subjects._ToDict(taxonomy, 'engineering', 2)
    self.assertTrue(isinstance(result, dict))
    self.assertEqual(2, len(result))
    self.assertEqual(9, len(result['engineering']))
    self.assertEqual(8, len(result['software/computation']))
    self.assertEqual('compilers', result['software/computation'][5]['i'])

  def testRootToJson(self):
    stream = StringIO.StringIO(_TEST_YAML)
    taxonomy = subjects._GetSubjectsTaxonomyFromYaml(stream)

    resultJson = subjects.GetSubjectsJson(taxonomy, None)
    self.assertTrue(isinstance(resultJson, basestring))

    result = simplejson.loads(resultJson)
    self.assertTrue(isinstance(result, list))

    self.assertEqual(None, result[0])
    result = result[1]
    self.assertEqual(2, len(result))
    self.assertEqual(9, len(result['root']))
    self.assertEqual(6, len(result['technology']))

    item = result['technology'][5]
    self.assertEqual('engineering', item['i'])
    self.assertEqual(False, item['l'])
