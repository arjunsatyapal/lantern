# !/usr/bin/python
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
import datetime
import itertools
import logging
import time
import unittest

# AppEngine imports
from google.appengine.ext import db
from google.appengine.api import users

# local imports
from demo import library
from demo import models
from demo import teacher_lib
import settings
import stubout

ROOT_PATH = settings.ROOT_PATH


class ClassroomTest(unittest.TestCase):
  """Tests for classroom and teacher dashboard classses."""

  def setUp(self):
    self.stubs = stubout.StubOutForTesting()
    self.teacher = users.get_current_user()
    self.math_course = library.create_new_doc(commit_message='For testing')
    self.math_course.title = 'Basic Math'
    self.math_course.label = models.AllowedLabels.COURSE
    self.math_course.tags = [db.Category('math')]
    self.math_course.grade_level = 3
    self.math_course.put()

    # Initialize accounts
    for idx, email in enumerate(('abc@gmail.com', 'ghi@gmail.com')):
      user_id = str(2984762 + idx)
      user = users.User(email=email, _user_id=user_id)
      models.Account.get_or_insert(
          '<%s>' % user_id, user=user, user_id=user_id, email=email,
          nickname=email, fresh=True)

    # Stub out mail
    self.mail_messages = []

    def _StubSendMail(sender, to, subject, body):
      self.mail_messages.append((sender, to, subject, body))

    self.stubs.SmartSet(teacher_lib.mail, 'send_mail', _StubSendMail)

  def tearDown(self):
    self.stubs.SmartUnsetAll()

  def testClassroomCreate(self):
    dt = datetime.datetime.strptime('2011-08-23', '%Y-%m-%d')
    classroom = teacher_lib.get_or_create_classroom(
        self.teacher, 'Fall 2011, Period 1', self.math_course, dt)
    self.assertTrue(isinstance(classroom, models.Classroom))

    self.assertEqual(self.teacher, classroom.user)
    self.assertEqual('Fall 2011, Period 1', classroom.name)
    self.assertEqual(self.math_course.trunk_ref, classroom.course_trunk_ref)
    self.assertEqual(self.math_course, classroom.course_doc_ref)
    self.assertEqual(dt, classroom.start_date)

    logging.info('%r', classroom.start_date)

    logging.info('Classroom key: %s, key name: %s' % (
        classroom.key(), classroom.key().name()))

    query = models.Classroom.all().filter('user =', self.teacher)
    self.assertEqual(1, query.count())
    c = query.get()
    logging.info('%r', c.start_date)

    query = models.Classroom.all().filter('user =', self.teacher).filter(
        'course_trunk_ref =', self.math_course.trunk_ref).filter(
        'name =', 'Fall 2011, Period 1')
    self.assertEqual(1, query.count())
    c = query.get()
    logging.info('%r', c.start_date)

    query = models.Classroom.all().filter('user =', self.teacher).filter(
        'course_trunk_ref =', self.math_course.trunk_ref).filter(
        'name =', 'Fall 2011, Period 1').filter(
        'start_date =', dt)
    self.assertEqual(1, query.count())


  def testClassroomCreate_ReturnsSame(self):
    dt = datetime.datetime.strptime('2011-08-23', '%Y-%m-%d')
    classroom = teacher_lib.get_or_create_classroom(
        self.teacher, 'Fall 2011, Period 1', self.math_course, dt)
    self.assertTrue(isinstance(classroom, models.Classroom))

    classroom1 = teacher_lib.get_or_create_classroom(
        self.teacher, 'Fall 2011, Period 1', self.math_course, dt)
    self.assertEqual(classroom.key(), classroom1.key())

  def testClassroomCreate_ReturnsNewIfDifferent(self):
    dt = datetime.datetime.strptime('2011-08-23', '%Y-%m-%d')
    classroom = teacher_lib.get_or_create_classroom(
        self.teacher, 'Fall 2011, Period 1', self.math_course, dt)
    self.assertTrue(isinstance(classroom, models.Classroom))

    classroom1 = teacher_lib.get_or_create_classroom(
        self.teacher, 'Fall 2011, Period 2', self.math_course, dt)
    self.assertNotEqual(classroom.key(), classroom1.key())

  def testEnrollment(self):
    dt = datetime.datetime.strptime('2011-08-23', '%Y-%m-%d')
    classroom = teacher_lib.get_or_create_classroom(
        self.teacher, 'Fall 2011, Period 1', self.math_course, dt)

    students = [
        'abc@gmail.com',
        'def@gmail.com',
        'ghi@gmail.com',
        ]
    result = teacher_lib.enroll_students(classroom, students)
    self.assertEqual(3, len(result))
    self.assertEqual(3, models.Enrollment.all().count())

    enrollment = dict((e.email, e) for e in result)
    self.assertFalse(enrollment['abc@gmail.com'].account_key.startswith(
        teacher_lib._PROVISIONAL_PREFIX))
    self.assertFalse(enrollment['ghi@gmail.com'].account_key.startswith(
        teacher_lib._PROVISIONAL_PREFIX))

    self.assertTrue(enrollment['def@gmail.com'].account_key.startswith(
        teacher_lib._PROVISIONAL_PREFIX))

  def testEnrollment_NoDuplicates(self):
    dt = datetime.datetime.strptime('2011-08-23', '%Y-%m-%d')
    classroom = teacher_lib.get_or_create_classroom(
        self.teacher, 'Fall 2011, Period 1', self.math_course, dt)

    students = [
        'abc@gmail.com',
        'def@gmail.com',
        'ghi@gmail.com',
        ]
    result = teacher_lib.enroll_students(classroom, students)
    self.assertEqual(3, len(result))
    self.assertEqual(3, models.Enrollment.all().count())

    students.extend([
        'jkl@gmail.com',
        'mno@gmail.com',
        ])
    result = teacher_lib.enroll_students(classroom, students)
    self.assertEqual(2, len(result))
    self.assertEqual(5, models.Enrollment.all().count())

  def testUnenroll(self):
    dt = datetime.datetime.strptime('2011-08-23', '%Y-%m-%d')
    classroom = teacher_lib.get_or_create_classroom(
        self.teacher, 'Fall 2011, Period 1', self.math_course, dt)

    students = [
        'abc@gmail.com',
        'def@gmail.com',
        'ghi@gmail.com',
        'jkl@gmail.com',
        'mno@gmail.com',
        ]
    result = teacher_lib.enroll_students(classroom, students)
    self.assertEqual(5, models.Enrollment.all().count())

    removal = [
        'abc@gmail.com',
        'jkl@gmail.com',
        'pqr@gmail.com',  # Not enrolled
        'stu@gmail.com',  # Not enrolled
        ]
    result = teacher_lib.unenroll_students(classroom, removal)
    self.assertEqual(2, len(result))
    self.assertEqual(3, models.Enrollment.all().count())

  def testGetEnrollment(self):
    dt = datetime.datetime.strptime('2011-08-23', '%Y-%m-%d')
    classroom = teacher_lib.get_or_create_classroom(
        self.teacher, 'Fall 2011, Period 1', self.math_course, dt)

    students = [
        'abc@gmail.com',
        'def@gmail.com',
        'ghi@gmail.com',
        'jkl@gmail.com',
        'mno@gmail.com',
        ]
    result = teacher_lib.enroll_students(classroom, students)
    self.assertEqual(5, len(teacher_lib.get_enrollment(classroom)))
    self.assertEqual(0, len(teacher_lib.get_enrollment(
        classroom, enrolled_only=True)))

  def testGetEnrollment_SomeEnrolled(self):
    dt = datetime.datetime.strptime('2011-08-23', '%Y-%m-%d')
    classroom = teacher_lib.get_or_create_classroom(
        self.teacher, 'Fall 2011, Period 1', self.math_course, dt)

    students = [
        'abc@gmail.com',
        'def@gmail.com',
        'ghi@gmail.com',
        'jkl@gmail.com',
        'mno@gmail.com',
        ]
    result = teacher_lib.enroll_students(classroom, students)
    for i in (0,3):
      result[i].is_enrolled = True
      result[i].put()
    self.assertEqual(2, len(teacher_lib.get_enrollment(
        classroom, enrolled_only=True)))

  def testInviteKey(self):
    dt = datetime.datetime.strptime('2011-08-23', '%Y-%m-%d')
    classroom = teacher_lib.get_or_create_classroom(
        self.teacher, 'Fall 2011, Period 1', self.math_course, dt)
    classroom1 = teacher_lib.get_or_create_classroom(
        self.teacher, 'Fall 2011, Period 2', self.math_course, dt)

    students = [
        'abc@gmail.com',
        'def@gmail.com',
        'ghi@gmail.com',
        'jkl@gmail.com',
        'mno@gmail.com',
        ]
    keys = []
    for student in students:
      keys.append(teacher_lib.get_invite_key(
          classroom, student, '<%s>' % student))

    for student, key in itertools.izip(students, keys):
      self.assertEqual(key, teacher_lib.get_invite_key(
          classroom, student, '<%s>' % student))
      key1 = teacher_lib.get_invite_key(
          classroom1, student, '<%s>' % student)

      logging.info('KEY: %s <> %s' % (key, key1))
      self.assertNotEqual(key, key1)

  def testAcceptInvite(self):
    dt = datetime.datetime.strptime('2011-08-23', '%Y-%m-%d')
    classroom = teacher_lib.get_or_create_classroom(
        self.teacher, 'Fall 2011, Period 1', self.math_course, dt)
    students = [
        'abc@gmail.com',
        'def@gmail.com',
        'ghi@gmail.com',
        'jkl@gmail.com',
        'mno@gmail.com',
        ]
    result = teacher_lib.enroll_students(classroom, students)
    enrollment = dict((e.email, e) for e in result)

    keys = []
    for student in students:
      keys.append(teacher_lib.get_invite_key(
          classroom, student, enrollment[student].account_key))

    # Doesn't have real ID
    user = users.User(email='def-new@gmail.com', _user_id='1938')
    result = teacher_lib.accept_enrollment_invite(
        classroom.key().name(), user, 'def@gmail.com', keys[1])
    self.assertTrue(result)

    enrolled = teacher_lib.get_enrollment(classroom, enrolled_only=True)
    self.assertEqual(1, len(enrolled))
    self.assertEqual('def@gmail.com', enrolled[0].email)
    self.assertEqual('def-new@gmail.com', enrolled[0].student.email())

  def testSendInvite(self):
    dt = datetime.datetime.strptime('2011-08-23', '%Y-%m-%d')
    classroom = teacher_lib.get_or_create_classroom(
        self.teacher, 'Fall 2011, Period 1', self.math_course, dt)
    students = [
        'abc@gmail.com',
        'def@gmail.com',
        'ghi@gmail.com',
        'jkl@gmail.com',
        'mno@gmail.com',
        ]
    result = teacher_lib.enroll_students(classroom, students)

    sent, bad = teacher_lib.send_enrollment_invitations(classroom)
    self.assertEqual(5, len(self.mail_messages))
    self.assertEqual(5, len(sent))
    self.assertEqual(0, len(bad))

    # Spot check
    for sender, to, subject, body in self.mail_messages:
      self.assertTrue('Basic Math' in subject)
      self.assertTrue('Basic Math' in body)
      self.assertTrue('Fall 2011' in body)
      self.assertTrue('class=' + classroom.key().name() in body)

    # Send again, ensure no new messages
    sent, bad = teacher_lib.send_enrollment_invitations(classroom)
    self.assertEqual(5, len(self.mail_messages))
    self.assertEqual(0, len(sent))
    self.assertEqual(0, len(bad))

  def testSendInvite_BadEmail(self):

    def _StubIsEmailValid(email):
      return email not in ('def@gmail.com', )

    self.stubs.SmartSet(teacher_lib.mail, 'is_email_valid', _StubIsEmailValid)

    dt = datetime.datetime.strptime('2011-08-23', '%Y-%m-%d')
    classroom = teacher_lib.get_or_create_classroom(
        self.teacher, 'Fall 2011, Period 1', self.math_course, dt)
    students = [
        'abc@gmail.com',
        'def@gmail.com',
        'ghi@gmail.com',
        'jkl@gmail.com',
        'mno@gmail.com',
        ]
    result = teacher_lib.enroll_students(classroom, students)

    sent, bad = teacher_lib.send_enrollment_invitations(classroom)
    self.assertEqual(4, len(self.mail_messages))
    self.assertEqual(4, len(sent))
    self.assertEqual(1, len(bad))

    self.assertEqual('def@gmail.com', bad[0])


if __name__ == "__main__":
  unittest.main()
