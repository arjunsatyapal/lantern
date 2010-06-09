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

# Python imports
import unittest

# local imports
from common import dewey_decimal


class DeweyDecimalTest(unittest.TestCase):
  """Tests the Dewey Decimal Classification (DDC) definitions."""

  def testDdcDivisionCount(self):
    self.assertEquals(100, len(dewey_decimal.GetDdcDivisions()))

  def testDdcDivisionByNumber(self):
    self.assertEquals(('900', 'Geography & history'),
                      dewey_decimal.GetDdcDivisionByNumber(900))
    self.assertEquals(('900', 'Geography & history'),
                      dewey_decimal.GetDdcDivisionByNumber('900'))

    self.assertEquals(('010', 'Bibliographies'),
                      dewey_decimal.GetDdcDivisionByNumber(10))
    self.assertEquals(('010', 'Bibliographies'),
                      dewey_decimal.GetDdcDivisionByNumber('010'))

  def testBadDdcDivisionByNumber(self):
    self.assertEquals(None, dewey_decimal.GetDdcDivisionByNumber(901))
    self.assertEquals(None, dewey_decimal.GetDdcDivisionByNumber(
        'Bibliographies'))

  def testDdcDivisionByDescription(self):
    self.assertEquals(
        ('900', 'Geography & history'),
        dewey_decimal.GetDdcDivisionByDescription('Geography & history'))

    self.assertEquals(
        ('010', 'Bibliographies'),
        dewey_decimal.GetDdcDivisionByDescription('Bibliographies'))

  def testBadDdcDivisionByDescription(self):
    self.assertEquals(
        None, dewey_decimal.GetDdcDivisionByDescription('No such topic'))
