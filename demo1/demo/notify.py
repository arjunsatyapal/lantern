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

# Local imports
import models


def watchedPages(user):
  """The set of pages the user is watching"""
  watched_pages = models.Subscription.all().filter('user =', user)
  # NEEDSWORK: handle recursive subscription, filtering "once-a-day"
  # subscription when run before the "end of the day", etc.
  return watched_pages


def sendChanges(user, result):
  """Send out summary of changes to watched pages.

  Args:
    user     : the user
    result   : an array of (trunk, old_tip, new_tip) tuples
  """
  logging.info("Notifying %s <%s>" % (user.nickname(), user.email()))
  for (trunk, old, new) in result:
    # NEEDSWORK: format the e-mail text here...
    logging.info("Trunk %s changed from %s to %s" %
                 (trunk.title, str(old), str(new)))
  # NEEDSWORK: ... and send it out to the user


def notifyUser(user):
  """Notify changes to a single user.

  Args:
    user    : a user who has subscription(s)
  """

  result = []

  for w in watchedPages(user):
    trunk = w.trunk
    changes_seen = (models.ChangesSeen.all().filter('user =', user).
         filter('trunk =', trunk))

    if not changes_seen.count():
      q = models.SubscriptionNotification.all().filter('trunk =', trunk)
    else:
      cutoff = changes_seen[0].timestamp
      q = (models.SubscriptionNotification.all().filter('trunk =', trunk).
           filter('timestamp >', cutoff))
    if not q.count():
      continue # nothing to report

    # Find the latest in case q has more than one
    latest_change = None
    for e in q:
      if not latest_change or latest_change.timestamp < e.timestamp:
        latest_change = e

    old_tip = None
    if changes_seen.count():
      old_tip = changes_seen[0].doc

    # Update the ChangesSeen record
    new_tip = db.get(trunk.head)
    timestamp = latest_change.timestamp
    if changes_seen.count():
      changes_seen[0].timestamp = timestamp
      changes_seen[0].doc = new_tip
    else:
      changes_seen = [models.ChangesSeen(trunk=trunk, user=user,
                                         doc=new_tip,
                                         timestamp=timestamp)]
    changes_seen[0].put()
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
