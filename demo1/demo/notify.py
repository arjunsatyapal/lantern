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

"""Notification-related functionality."""

# Python imports
import logging

# AppEngine imports
from google.appengine.ext import db
from google.appengine.api.labs import taskqueue
from google.appengine.api import mail

# Local imports
import models

# The sender address
LANTERN_SENDER = 'lantern@example.xz'


def watchedPages(user):
  """The set of pages the user is watching"""
  watched_pages = (models.Subscription.all().
                   filter('user =', user).
                   filter('method !=', models.Subscription.METH_MEH))
  # NEEDSWORK: handle recursive subscription, filtering "once-a-day"
  # subscription when run before the "end of the day", etc.
  return watched_pages


def isPageWatched(user, trunk):
  """Is the page being watched by the user?"""
  result = (models.Subscription.all().
            filter('user =', user).
            filter('trunk =', trunk).
            filter('method !=', models.Subscription.METH_MEH))
  return result.count(1) != 0


def sendChanges(user, result):
  """Send out summary of changes to watched pages.

  Args:
    user: the user
    result: an array of (trunk, old_tip, new_tip) tuples
  """
  logging.info("Notifying %s <%s>" % (user.nickname(), user.email()))
  body = []
  for (trunk, old, new) in result:
    logging.info("Trunk %s changed from %s to %s" %
                 (trunk.title, str(old), str(new)))
    # NEEDSWORK: format the e-mail text a bit better here...
    body.append("Page '%s' changed from '%s' to '%s'\n" %
                (trunk.title, str(old), str(new)))
  mail.send_mail(sender=LANTERN_SENDER,
                 to=user.email(),
                 subject="Recent changes to the Lantern pages",
                 body="".join(body))

def notifyUser(user):
  """Notify changes to a single user.

  Args:
    user: a user who has subscription(s)
  """
  result = []

  for w in watchedPages(user):
    trunk = w.trunk

    # Be defensive by making sure the latest one, if more than one row
    # exists for whatever reason, is used.  ChangesSeen is supposed to
    # have a single row per <user, trunk> tuple; it is used to record
    # the last timestamp of the changes we noticed and sent e-mail about
    # to the user on the trunk, so the latest timestamp matters.
    changes_seen = (models.ChangesSeen.all().filter('user =', user).
                    filter('trunk =', trunk).
                    order('-timestamp'))

    if not changes_seen.count(1):
      cutoff = None
    else:
      cutoff = changes_seen[0].timestamp

    q = (models.SubscriptionNotification.all().
         filter('trunk =', trunk).
         order('-timestamp'))
    if cutoff:
      q.filter('timestamp >', cutoff)
    if not q.count(1):
      continue # nothing to report

    latest_change = q[0]
    old_tip = None
    if changes_seen.count(1):
      old_tip = changes_seen[0].doc

    # Update the ChangesSeen record
    new_tip = db.get(trunk.head)
    timestamp = latest_change.timestamp
    if changes_seen.count(1):
      change_info = changes_seen[0]
      change_info.timestamp = timestamp
      change_info.doc = new_tip
      # Make sure ChangesSeen has a singleton per <user, trunk>
      # by removing older ones.  Unfortunately, we cannot iterate
      # over changes_seen[1:] as "Open-ended slices are not supported"
      first = True
      for extra in changes_seen:
        if first:
          first = False
        else:
          extra.delete()
    else:
      change_info = models.ChangesSeen(trunk=trunk, user=user,
                                       doc=new_tip,
                                       timestamp=timestamp)
    change_info.put()
    result.append((trunk, old_tip, new_tip))

  if result:
    sendChanges(user, result)


def queueNotify(subscription):
  notifyURL = '/task/notifyUser'
  logging.info("queueing notification for %s" % subscription.user.nickname())
  taskqueue.add(url=notifyURL, params={'s': str(subscription.key())})


def notifyAll():
  """Main entry point of notification "cron job"

  Scan all the subscriptions to find whom to notify, and fire
  an asynchronous task 'notifyUser' for each of them.
  """
  query = models.Subscription.all().order('user')
  subscription = None
  for e in query:
    if subscription and subscription.user != e.user:
      queueNotify(subscription)
    subscription = e

  if subscription:
    queueNotify(subscription)
