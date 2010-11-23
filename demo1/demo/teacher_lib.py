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

"""Library methods for teacher-related activity."""

import hashlib
import hmac
import logging
import os

from google.appengine.api import mail
from google.appengine.api import users
from google.appengine.ext import db

import django.template.loader

# Lantern imports
import library
import models


class Error(Exception):
  """General module-level errors."""


class NoSuchClassroomError(Error):
  """Cannot find specified classroom."""


class InvalidInvitationError(Error):
  """Cannot verify invitation."""


class InvalidTeacherError(Error):
  """Only the teacher may send invites."""


def get_or_create_classroom(teacher, name, course, start_date):
  """Gets or creates a classroom for the specified teacher.

  If the specified classroom does not yet exist, creates a new instance.

  Args:
    teacher: A User object representing the teacher setting up the course.
    name: A descriptive name for the class to be taught. For example,
        "Fall 2011 1st Period".
    course: A DocModel for the course to be taught.
    start_date: The datetime.datetime object corresponding to when the class
        is to start.

  Returns:
    An instance of Classroom.
  """
  classroom = models.Classroom.all().filter('user =', teacher).filter(
      'course_trunk_ref =', course.trunk_ref).filter(
      'name = ', name).filter(
      'start_date =', start_date).get()
  if not classroom:
    classroom = library.insert_with_new_key(
        models.Classroom,
        user=teacher,
        name=name,
        start_date=start_date,
        course_trunk_ref=course.trunk_ref,
        course_doc_ref=course)
  return classroom


def enroll_students(classroom, students):
  """Enroll specified students in the class.

  Args:
    classroom: The Classroom to which students are enrolled.
    students: List of email addresses of students to enroll. Only new students
        are enrolled.
  Returns:
    List of newly enrolled Enrollment entries.
  """
  new_students = set(students)
  existing_students = classroom.enrollment_set.fetch(classroom.max_enrollment)
  if existing_students:
    enrolled_set = set((student.email for student in existing_students))
    new_students -= enrolled_set
  new_entries = []
  for email in new_students:
    entry = library.insert_with_new_key(
        models.Enrollment,
        classroom=classroom,
        email=email)
    new_entries.append(entry)
  return new_entries


def get_enrollment(classroom, enrolled_only=False):
  """Gets the list of students that have enrolled.

  Args:
    classroom: The classroom whose enrollment to get.
    enrolled_only: If True, only return the set that are enrolled. Default is
        False.
  Returns:
    Set of Enrollment entries for the classroom.
  """
  if enrolled_only:
    query = classroom.enrollment_set.filter('is_enrolled =', True)
  else:
    query = classroom.enrollment_set
  return query.fetch(classroom.max_enrollment)


def unenroll_students(classroom, students):
  """Unenroll specified students from the class.

  Args:
    classroom: The Classroom to which students are enrolled.
    students: List of email addresses of students to remove from the roster.

  Returns:
    List of emails that were removed.
  """
  students_to_delete = set(students)
  existing_students = classroom.enrollment_set.fetch(classroom.max_enrollment)

  removals = [student for student in existing_students
              if student.email in students_to_delete]
  values = []
  if removals:
    values = [student.email for student in removals]
    db.delete(removals)
  return values


def get_invite_key(classroom, student_email):
  """Gets an invitation key.

  This is signed using the teacher's secret.

  Args:
    classroom: The classroom issuing the invite.
    student_email: The email address of the student.

  Returns:
    A string representing the key. The acceptance must include this key, which
    presumably is hard to forge.
  """
  teacher = classroom.user
  teacher_account = models.Account.get_account_for_user(teacher)
  token = teacher_account.get_xsrf_token()  # Makes sure secret is created

  email_str = student_email.lower()
  if isinstance(email_str, unicode):
    email_str = email_str.encode('utf-8')
  h = hmac.new(teacher_account.xsrf_secret, email_str, hashlib.sha1)
  h.update(str(classroom.key()))
  h.update(str(teacher_account.created))
  h.update(str(classroom.start_date))
  return h.hexdigest()


def accept_enrollment_invite(classroom_key, student, invite_key):
  """Accepts enrollment invitation, enrolling the student.

  The student is enrolled if we can verify the invitation key using the
  student's email. The caller is expected to pass in the current user as
  student, so that only the currently logged in user can accept the
  invitation for him/herself.

  Args:
    classroom_key: The DB key for the classroom.
    student: User object representing the invitee.
    invite_key: The invitation key.

  Returns:
    True if enrolled.
  Raises:
    NoSuchClassroomError: If specified classroom cannot be found.
    InvalidInvitationError: If the invitation is corrupted.
  """
  classroom = models.Classroom.get_by_key_name(classroom_key)
  if not classroom:
    raise NoSuchClassroomError('Invalid classroom specified by %s' %
                               classroom_key)
  key = get_invite_key(classroom, student.email())
  if key != invite_key:
    raise InvalidInvitationError('Cannot validate invitation')

  entry = classroom.enrollment_set.filter('email =', student.email()).get()
  if not entry:
    raise InvalidInvitationError('Cannot locate enrollment record for %s' %
                                 student.email())
  # Validated, so get enrollment and mark as
  entry.is_enrolled = True
  entry.student = student
  entry.put()
  return True


def send_enrollment_invitations(classroom):
  """Sends invitation to the students.

  Args:
    classroom: The Classroom for which the invitations are issued.
  Returns:
    A tuple of (sent_emails, bad_emails), where:
      sent_emails: List of email addresses to which invites were sent.
      bad_email: List of email addresses that were deemed invalid.
  Raises:
    InvalidTeacherError: Current user is not the classroom teacher.
  """
  user = users.get_current_user()
  if user.user_id() != classroom.user.user_id():
    raise InvalidTeacherError(
        'Only the classroom teacher may send invitations.')
  context = {
      'classroom': classroom,
      'server': os.environ['SERVER_NAME'],
      }
  sender = user.email()
  subject = django.template.loader.render_to_string(
      'include/class_invite_subject.txt', context).strip()

  sent_emails = []
  bad_emails = []
  for student in classroom.enrollment_set.fetch(classroom.max_enrollment):
    if student.is_invited:
      continue
    if not mail.is_email_valid(student.email):
      bad_emails.append(student.email)
      continue
    context['key'] = get_invite_key(classroom, student.email)
    body = django.template.loader.render_to_string(
        'include/class_invite_body.txt', context)
    mail.send_mail(sender=sender, to=student.email, subject=subject, body=body)
    sent_emails.append(student.email)

    # Prevent spam
    student.is_invited = True
    student.put()
  return sent_emails, bad_emails
