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

class AccountTest(unittest.TestCase):
  """Tests the Account model."""

  def testAccountForCurrentUser(self):
    q = db.Query(models.Account)
    self.assertEquals(0, q.count())

    user = users.get_current_user()
    account = models.Account.get_account_for_user(user)
    self.assertEquals(user.user_id(), account.user_id)
    account.put()

    q = db.Query(models.Account)
    self.assertEquals(1, q.count())

    a1 = db.get(account.key())
    self.assertEquals(user.email(), a1.email)
    logging.info(a1.email)

  def testAccountKeyNameIsBasedOnId(self):
    user = users.get_current_user()
    account = models.Account.get_account_for_user(user)

    self.assertEquals("<%s>" % user.user_id(),
                      account.key().name())

  def testInnsertWithSameKeyNameOverwrites(self):
    user = users.get_current_user()
    account = models.Account.get_account_for_user(user)
    account.put()

    # Another account created using the same user ID
    new_user = users.User(email='me@sample.com', _user_id=user.user_id())
    account1 = models.Account.get_account_for_user(new_user)
    account1.put()

    q = db.Query(models.Account)
    self.assertEquals(1, q.count())

    # Another account created using a differentd ID creates new record.
    new_user = users.User(email='me@sample.com', _user_id='30029384')
    account2 = models.Account.get_account_for_user(new_user)
    account2.put()

    q = db.Query(models.Account)
    self.assertEquals(2, q.count())

  def testNickname(self):
    user = users.User('jackKlein@somedomain.com', _user_id='299910294181029')
    account = models.Account.get_account_for_user(user)

    self.assertEquals('jackKlein', account.nickname)

  def testLowercaseEmailAndNickname(self):
    user = users.User('jackKlein@somedomain.com', _user_id='299910294181029')
    account = models.Account.get_account_for_user(user)

    self.assertEquals('jackKlein', account.nickname)

    self.assertEquals('jackklein@somedomain.com', account.lower_email)
    self.assertEquals('jackklein', account.lower_nickname)

  def testDuplicateEmailName(self):
    user = users.User('joe@somedomain.com', _user_id='299910294181029')
    account = models.Account.get_account_for_user(user)
    account.put()

    user = users.User('joe@another.com', _user_id='20005762003')
    account1 = models.Account.get_account_for_user(user)

    self.assertEquals('joe', account.nickname)
    self.assertEquals('joe1', account1.nickname)

  def testGetAccountByKeyName(self):
    user = users.User('joe@somedomain.com', _user_id='299910294181029')
    account = models.Account.get_account_for_user(user)
    account.put()

    user = users.User('joe@another.com', _user_id='20005762003')
    account1 = models.Account.get_account_for_user(user)
    account1.put()

    acc = models.Account.get_by_key_name(
        '<%s>' % '299910294181029')

    self.assertEqual(user, account1.user)

  def testGetNicknameForId(self):
    user = users.User('joe@somedomain.com', _user_id='299910294181029')
    account = models.Account.get_account_for_user(user)
    account.put()

    nickname = models.Account.get_nickname_for_id('299910294181029')
    self.assertEquals('joe', nickname)

    nickname = models.Account.get_nickname_for_id('3939')
    self.assertEquals('user_3939', nickname)

    nickname = models.Account.get_nickname_for_id('3939', 'foo_user')
    self.assertEquals('foo_user', nickname)


  def testAccountForEmail(self):
    user = users.User('joe@somedomain.com', _user_id='299910294181029')
    account = models.Account.get_account_for_user(user)
    account.put()

    user = users.User('joe3@somedomain.com', _user_id='099292817262')
    account = models.Account.get_account_for_user(user)
    account.put()

    accounts = models.Account.get_accounts_for_email('joe@somedomain.com')
    self.assertTrue(isinstance(accounts, list))
    self.assertEquals(1, len(accounts))
    self.assertTrue(accounts[0].user_id, '299910294181029')

  def testMultipleAccountForEmail(self):
    user = users.User('joe@somedomain.com', _user_id='299910294181029')
    account = models.Account.get_account_for_user(user)
    account.put()

    user = users.User('joe@somedomain.com', _user_id='099292817262')
    account = models.Account.get_account_for_user(user)
    account.put()

    accounts = models.Account.get_accounts_for_email('joe@somedomain.com')
    self.assertTrue(isinstance(accounts, list))
    self.assertEquals(2, len(accounts))

  def testMultipleAccountForNickname(self):
    user = users.User('joe@somedomain.com', _user_id='299910294181029')
    account = models.Account.get_account_for_user(user)
    account.put()

    user = users.User('joe@somedomain.com', _user_id='099292817262')
    account = models.Account.get_account_for_user(user)
    account.put()

    accounts = models.Account.get_accounts_for_nickname('joe')
    self.assertTrue(isinstance(accounts, list))
    self.assertEquals(1, len(accounts))

    self.assertEquals([], models.Account.get_accounts_for_nickname('foo'))

  def testNicknameForEmail(self):
    user = users.User('joe@somedomain.com', _user_id='299910294181029')
    account = models.Account.get_account_for_user(user)
    account.put()

    user = users.User('joe@somedomain.com', _user_id='099292817262')
    account = models.Account.get_account_for_user(user)
    account.put()

    nickname = models.Account.get_nickname_for_email('joe@somedomain.com')
    self.assertTrue(nickname in ('joe', 'joe1'))

  def testEmailForNicknname(self):
    user = users.User('joe@somedomain.com', _user_id='299910294181029')
    account = models.Account.get_account_for_user(user)
    account.put()

    user = users.User('jim@somedomain.com', _user_id='09929281726239')
    account = models.Account.get_account_for_user(user)
    account.put()

    user = users.User('joe@somedomain.com', _user_id='099292817262')
    account = models.Account.get_account_for_user(user)
    account.put()

    email = models.Account.get_email_for_nickname('joe1')
    self.assertEquals('joe@somedomain.com', email)

  def testUserHasSelectedNickname(self):
    user = users.User('joe@somedomain.com', _user_id='299910294181029')
    account = models.Account.get_account_for_user(user)
    account.put()

    self.assertFalse(account.user_has_selected_nickname())

  def testXsrfToken(self):
    user = users.User('joe@somedomain.com', _user_id='299910294181029')
    account = models.Account.get_account_for_user(user)
    account.put()

    self.assertEquals(None, account.xsrf_secret)
    secret = account.get_xsrf_token()
    self.assertNotEquals(None, secret)
    self.assertNotEquals(None, account.xsrf_secret)

    # Idempotent?
    self.assertEquals(secret, account.get_xsrf_token())

  def testAccountProperties(self):
    user = users.get_current_user()
    account = models.Account.get_account_for_user(user)
    self.assertEquals(user.user_id(), account.user_id)
    account.put()

    a1 = models.Account.get_or_insert(
        ('<%s>' % user.user_id()), **account.properties())

    self.assertEquals(user.email(), a1.email)
    logging.info(a1.email)


if __name__ == "__main__":
  unittest.main()
