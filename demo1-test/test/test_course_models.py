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

class PedagogyTest(unittest.TestCase):
  """Tests the base model for pedagogical items."""

  def testGetRandomString(self):
    random = models.PedagogyModel.gen_random_string(32)
    self.assertEquals(32, len(random))

  def testGetRandomStringNoCollisions(self):
    keys = set()
    for i in xrange(100):
      random = models.PedagogyModel.gen_random_string(4)
      keys.add(random)
      self.assertEquals(4, len(random))

    # Check for no collisions
    self.assertEquals(100, len(keys))

  def testInsertWithRandomKey(self):
    user = users.get_current_user()
    course = models.Course.insert_with_random_key(
        None, 32,
        title='Test Course',
        creator=user,
        description='Defining moments of testing.')

    logging.info("Course key: ***%s***", course.key().name())
    self.assertEquals('Test Course', course.title)
    self.assertEquals(user, course.creator)

    record = models.Course.gql('WHERE title = :1', 'Test Course').get()
    self.assertEquals(course.key(), record.key())

  def testInsertWithRandomKeyWithCollision(self):
    user = users.get_current_user()
    course = models.Course.get_or_insert(
        'foo',
        title='Random Course',
        creator=user,
        description='Describes perils of random testing.')

    # Monkey patch to test collision
    orig_gen_random_string = models.Course.gen_random_string
    call_count = [0]

    class Callable(object):
      """Callable to fake out gen_random_sring."""
      def __init__(self, course_class):
        self.course_class = course_class
        self.call_count = 0

      def __call__(self, num_chars):
        self.call_count += 1
        if self.call_count < 3:
          return 'foo'
        return 'bar'

    fixed_string = Callable(models.Course)
    models.Course.gen_random_string = fixed_string

    course = models.Course.insert_with_random_key(
        None, 3,
        title='Test Course',
        creator=user,
        description='Defining moments of testing.')

    # Restore class method.
    models.Course.gen_random_string = orig_gen_random_string

    self.assertEquals('bar', course.key().name())
    self.assertEquals('Test Course', course.title)
    self.assertEquals(user, course.creator)
    self.assertEquals(3, fixed_string.call_count)

    self.assertEquals(2, models.Course.all().count())

  def setUpBasicCourse(self):
    """Sets up a course with 3 lessons."""
    user = users.get_current_user()

    course = models.Course.insert_with_random_key(
        None, 32,
        title='Test Course',
        creator=user,
        description='Defining moments of testing.')

    course_key = course.key().name()

    lessons = []
    lessons.append(models.CourseLesson.insert_with_random_key(
        course_key, 4,
        title='Lesson 1',
        creator=user))
    lessons.append(models.CourseLesson.insert_with_random_key(
        course_key, 4,
        title='Lesson 2',
        creator=user))
    lessons.append(models.CourseLesson.insert_with_random_key(
        course_key, 4,
        title='Lesson 3',
        creator=user))

    for i, lesson in enumerate(lessons):
      ref = models.LessonRef(
          parent=course,
          reference=lesson.key(),
          ordinal=i,
          section_label=('Chapter %d' % i))
      ref.put()

    return course

  def testCourseWithLessons(self):
    course = self.setUpBasicCourse()
    count = 0
    for ref in models.LessonRef.all().ancestor(course).order('ordinal'):
      self.assertEquals(count, ref.ordinal)
      count += 1
      self.assertEquals('Lesson %d' % count, ref.get_reference().title)
    self.assertEquals(3, count)


  def testGetReferences(self):
    course = self.setUpBasicCourse()

    count = 0
    for ref in course.get_references(models.LessonRef):
      self.assertEquals(count, ref.ordinal)
      count += 1
      self.assertEquals('Lesson %d' % count, ref.get_reference().title)
    self.assertEquals(3, count)


  def testCourseInheritanceWithNoOverride(self):
    # Sets up a course with 3 lessons.
    orig_course = self.setUpBasicCourse()

    user = users.get_current_user()
    course = models.Course.insert_with_random_key(
        None, 32,
        title='My Test Course',
        creator=user,
        description='My variant.',
        template_reference=orig_course)

    # No actual overrides.
    count = 0
    for ref in course.get_references(models.LessonRef):
      self.assertEquals(count, ref.ordinal)
      count += 1
      self.assertEquals('Lesson %d' % count, ref.get_reference().title)
    self.assertEquals(3, count)

  def testCourseInheritanceWithSomeOverrides(self):
    # Sets up a course with 3 lessons.
    orig_course = self.setUpBasicCourse()

    user = users.get_current_user()
    course = models.Course.insert_with_random_key(
        None, 32,
        title='My Test Course',
        creator=user,
        description='My variant.',
        template_reference=orig_course)

    course_key = course.key().name()

    lesson = models.CourseLesson.insert_with_random_key(
        course_key, 4,
        title='Lesson 2a',
        creator=user)

    ref = models.LessonRef(
        parent=course,
        reference=lesson.key(),
        ordinal=1,
        section_label=('Chapter 2'))
    ref.put()

    count = 0
    for ref in course.get_references(models.LessonRef):
      self.assertEquals(count, ref.ordinal)
      count += 1
      if count == 2:
        self.assertEquals('Lesson %da' % count, ref.get_reference().title)
      else:
        self.assertEquals('Lesson %d' % count, ref.get_reference().title)
    self.assertEquals(3, count)

  def testCourseInheritanceWithDelete(self):
    # Sets up a course with 3 lessons.
    orig_course = self.setUpBasicCourse()

    user = users.get_current_user()
    course = models.Course.insert_with_random_key(
        None, 32,
        title='My Test Course',
        creator=user,
        description='My variant.',
        template_reference=orig_course)

    course_key = course.key().name()

    ref = models.LessonRef(
        parent=course,
        ordinal=1,
        section_label=('Chapter 2'))
    ref.put()

    count = 0
    for ref in course.get_references(models.LessonRef):
      count += 1
      if count == 1:
        self.assertEquals(0, ref.ordinal)
        self.assertEquals('Lesson 1', ref.get_reference().title)
      else:
        self.assertEquals(2, ref.ordinal)
        self.assertEquals('Lesson 3', ref.get_reference().title)
    self.assertEquals(2, count)

  def testCourseInheritanceWithAddition(self):
    # Sets up a course with 3 lessons.
    orig_course = self.setUpBasicCourse()

    user = users.get_current_user()
    course = models.Course.insert_with_random_key(
        None, 32,
        title='My Test Course',
        creator=user,
        description='My variant.',
        template_reference=orig_course)

    course_key = course.key().name()
    lessons = []
    lessons.append(models.CourseLesson.insert_with_random_key(
        course_key, 4,
        title='Preface',
        creator=user))
    lessons.append(models.CourseLesson.insert_with_random_key(
        course_key, 4,
        title='Appendix',
        creator=user))

    ref = models.LessonRef(
        parent=course,
        reference=lessons[0].key(),
        ordinal=-1,
        section_label='Preface')
    ref.put()

    ref = models.LessonRef(
        parent=course,
        reference=lessons[1].key(),
        ordinal=10,
        section_label='Appendix')
    ref.put()

    count = 0
    refs = list(course.get_references(models.LessonRef))

    ref = refs[0]
    self.assertEquals(-1, ref.ordinal)
    self.assertEquals('Preface', ref.get_reference().title)

    ref = refs[4]
    self.assertEquals(10, ref.ordinal)
    self.assertEquals('Appendix', ref.get_reference().title)

    self.assertEquals(5, len(refs))


if __name__ == "__main__":
  unittest.main()
