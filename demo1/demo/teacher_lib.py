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

import datetime
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


# Prefix for provisional accounts.
_PROVISIONAL_PREFIX = 'p:'

# Invitation expires a number of days after the class started.
_INVITATION_EXPIRE_DAYS = 30


class Error(Exception):
  """General module-level errors."""


class NoSuchClassroomError(Error):
  """Cannot find specified classroom."""


class MaxEnrollmentError(Error):
  """Maximum enrollment reached."""


class InvalidInvitationError(Error):
  """Cannot verify invitation."""


class InvalidTeacherError(Error):
  """Only the teacher may send invites."""


class InvitationExpiredError(Error):
  """Invitation has expired."""


class InvitationAlreadyAcceptedError(Error):
  """Invitation was already accepted."""


def get_or_create_classroom(teacher, name, course, start_date,
                            max_enrollment=None):
  """Gets or creates a classroom for the specified teacher.

  If the specified classroom does not yet exist, creates a new instance.

  Args:
    teacher: A User object representing the teacher setting up the course.
    name: A descriptive name for the class to be taught. For example,
        "Fall 2011 1st Period".
    course: A DocModel for the course to be taught.
    start_date: The datetime.datetime object corresponding to when the class
        is to start.
    max_enrollment: Maximum of students to be enrolled. If not specified, uses
        the model's default value of 100.

  Returns:
    An instance of Classroom.
  """
  max_enrollment = max_enrollment or models.Classroom.DEFAULT_MAX_ENROLLMENT
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
        course_doc_ref=course,
        max_enrollment=max_enrollment)
  return classroom


def enroll_student(classroom, student_email):
  """Enroll specified student in the class using email.

  The implementation looks up the Account for the specified email. If it does
  not exist (as either Account or ProvisionalAccount), a ProvisionalAccount is
  created for the student.

  The enroll a student, the email is needed to send the invitation. We use the
  email only to identify the enrollment record when the user accepts the
  invitation. Subequently, the User object will be used to track progress.

  Args:
    classroom: The Classroom to which students are enrolled.
    student: Email addresses of a student to enroll.
  Returns:
    Account or ProvisionalAccount.
  """
  accounts = models.Account.get_accounts_for_email(student_email)
  if accounts:
    # TODO(vchen): What do we really do if there are more than one?
    account_key = accounts[0].key().name()
  else:
    account = models.ProvisionalAccount.get_or_create_account_for_email(
        student_email)
    account_key = _PROVISIONAL_PREFIX + account.key().name()
  entry = library.insert_with_new_key(
      models.Enrollment,
      classroom=classroom,
      account_key=account_key,
      email=student_email)
  return entry


def enroll_students(classroom, students):
  """Enroll specified students in the class.

  Args:
    classroom: The Classroom to which students are enrolled.
    students: List of email addresses of students to enroll. Only new students
        are enrolled.
  Returns:
    List of newly enrolled Enrollment entries.
  Raises:
    MaxEnrollmentError: The call would cause max_enrollment to be exceeded.
        No new students are added.
  """
  new_students = set(students)
  existing_students = classroom.enrollment_set
  total = len(new_students)
  if existing_students.count(1):  # If at least 1, then get emails.
    enrolled_set = set((student.email for student in existing_students))
    new_students -= enrolled_set
    total = len(enrolled_set) + len(new_students)

  # Validate max enrollment
  if total > classroom.max_enrollment:
    raise MaxEnrollmentError(
        'Total enrollment of %d would exceed maximum of %d. Please change the '
        'limit or remove some entries' % (total, classroom.max_enrollment))
  new_entries = []
  for email in new_students:
    entry = enroll_student(classroom, email)
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
  existing_students = classroom.enrollment_set

  removals = [student for student in existing_students
              if student.email in students_to_delete]
  values = []
  if removals:
    values = [student.email for student in removals]
    db.delete(removals)
  return values


def get_invite_key(classroom, student_email, account_key):
  """Gets an invitation key.

  This is signed using the teacher's secret.

  Args:
    classroom: The classroom issuing the invite.
    student_email: The email address of the student.
    account_key: The key name of an Account or ProvisionalAccount associated
        with the email. If it starts with _PROVISIONAL_PREFIX, then it is
        a provisional account.

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
  h.update(account_key)
  h.update(str(classroom.key()))
  h.update(str(teacher_account.created))
  h.update(str(classroom.start_date))
  return h.hexdigest()


def accept_enrollment_invite(
    classroom_key, student_user, student_email, invite_key):
  """Accepts enrollment invitation, enrolling the student.

  The student is enrolled if we can verify the invitation key using the
  student's email. The caller is expected to pass in the current user as
  student, so that only the currently logged in user can accept the
  invitation for him/herself.

  NOTE: It is possible for someone other than the intended to accept the
  invitation, because we are not requiring email to match.

  Args:
    classroom_key: The DB key for the classroom.
    student_user: User object representing the invitee.
    student_email: Email used in the invitation. It does not have to be the same
        as student_user.email.
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

  # TODO(vchen): Should expiration should be tied to enrollment record
  # instead to allow late comers? Or if the class start is not really relevant?
  expiration = classroom.start_date + datetime.timedelta(
      days=_INVITATION_EXPIRE_DAYS)
  if datetime.datetime.now() > expiration:
    raise InvitationExpiredError('Invitation has expired.')

  entry = classroom.enrollment_set.filter('email =', student_email).get()
  if not entry:
    raise InvalidInvitationError('Cannot locate enrollment record for %s' %
                                 student_email)

  key = get_invite_key(classroom, student_email, entry.account_key)
  if key != invite_key:
    raise InvalidInvitationError('Cannot validate invitation: %s, %s' %
                                 (student_email, entry.account_key))

  if entry.student and entry.student != student_user:
    raise InvitationAlreadyAcceptedError(
        'Invitation was already accepted by another user')

  # Validated, so mark as enrolled by the specified user.
  entry.is_enrolled = True
  entry.student = student_user
  entry.put()

  if entry.account_key.startswith(_PROVISIONAL_PREFIX):
    account = models.ProvisionalAccount.get_by_key_name(
        entry.account_key[len(_PROVISIONAL_PREFIX):])
    account.real_account = models.Account.get_account_for_user(student_user)
    account.put()
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
  if user != classroom.user:
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
  for enrollment in classroom.enrollment_set:
    if enrollment.is_invited:
      continue
    if not mail.is_email_valid(enrollment.email):
      bad_emails.append(enrollment.email)
      continue
    context['email'] = enrollment.email
    context['key'] = get_invite_key(
        classroom, enrollment.email, enrollment.account_key)
    body = django.template.loader.render_to_string(
        'include/class_invite_body.txt', context)
    mail.send_mail(
        sender=sender, to=enrollment.email, subject=subject, body=body)
    sent_emails.append(enrollment.email)

    # Prevent spam
    enrollment.is_invited = True
    enrollment.put()
  return sent_emails, bad_emails
