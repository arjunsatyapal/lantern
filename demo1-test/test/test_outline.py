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
from demo import outline

_TEST_DOC = """
%YAML 1.2
---
kind: Course
title: AP CS Python
description: >
  An AP-level course for Computer Science using Python
ddc: '000'  # Dewey Decimal
labels:     # Tags
  - AP
  - CS
  - Python
grade_level: 10
is_published: true
creator: test@example.com
creator_id: 09029387462
created: 2010-05-10 12:00
key: alkei20384mp3akk093j+k39nl33
lessons:  # Implicit kink: CourseLesson
  - section_label: Chapter 1
    title: Introduction
    key: ...
    modules:
      - section_label: '1.1'
        title: Foo
        key: plkjerkjep
      - section_label: '1.2'
        title: Bar
        key: kjrjejpaer
  - section_label: Chapter 2
    title: Getting Started
    key: ...
    modules:
      - section_label: '2.1'
        title: Foo
        key: abcccdd
"""


class OutlineTest(unittest.TestCase):
  """Tests for outlining."""

  def testLoadDoesNotFail(self):
    loader = outline.CourseOutline()
    courses = loader.Load(_TEST_DOC)
    self.assertEquals(1, len(courses))

  def testLoadCheckCourse(self):
    loader = outline.CourseOutline()
    courses = loader.Load(_TEST_DOC)
    course = courses[0]
    self.assertEquals('AP CS Python', course.title)

    self.assertEquals(3, len(course.labels))
    self.assertEquals(10, course.grade_level)
    self.assertEquals('000', course.ddc)

    self.assertEquals(2, len(course.get_lessons()))

  def testLoadCheckLessons(self):
    loader = outline.CourseOutline()
    courses = loader.Load(_TEST_DOC)
    course = courses[0]

    lessons = course.get_lessons()
    self.assertEquals('Introduction', lessons[0].get_reference().title)
    self.assertEquals('Getting Started', lessons[1].get_reference().title)

    for lesson in lessons:
      self.assertEquals(3, len(lesson.get_reference().labels))
      self.assertEquals(10, lesson.get_reference().grade_level)
      self.assertEquals('000', lesson.get_reference().ddc)

  def testLoadCheckModules(self):
    loader = outline.CourseOutline()
    courses = loader.Load(_TEST_DOC)
    course = courses[0]

    lessons = course.get_lessons()
    lesson = lessons[0]

    modules = lesson.get_reference().get_modules()
    self.assertEquals(2, len(modules))

    self.assertEquals('Foo', modules[0].get_reference().title)
    self.assertEquals('Bar', modules[1].get_reference().title)

    for lesson in modules:
      self.assertEquals(3, len(lesson.get_reference().labels))
      self.assertEquals(10, lesson.get_reference().grade_level)
      self.assertEquals('000', lesson.get_reference().ddc)

  def testDumpFromLoad(self):
    loader = outline.CourseOutline()
    courses = loader.Load(_TEST_DOC)
    course = courses[0]

    txt = loader.Dump(course)

    # Spot-check some expected strings
    self.assertTrue(txt.startswith('%YAML'))

    self.assertTrue('---' in txt)
    # Top-level
    self.assertTrue('key: alkei20384mp3akk093j+k39nl33' in txt)

    # Module-level
    self.assertTrue("    section_label: '1.1'" in txt)
    logging.info("=========== %s", txt)

  def testStoreFromLoad(self):
    loader = outline.CourseOutline()
    courses = loader.Load(_TEST_DOC)

    course = loader.Store(courses[0])
    txt = loader.Dump(course)
    logging.info("=========== %s", txt)

    self.assertTrue(course.is_saved())

    # Spot-check some expected strings
    self.assertTrue(txt.startswith('%YAML'))

    self.assertTrue('---' in txt)
    # Top-level
    self.assertTrue(
        "key: !!python/unicode 'alkei20384mp3akk093j+k39nl33'" in txt)

    # Module-level
    self.assertTrue("    section_label: !!python/unicode '1.1'" in txt)


if __name__ == "__main__":
  unittest.main()
