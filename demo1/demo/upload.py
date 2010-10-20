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

"""Upload-related functionality."""

# Python imports
import cgi
import csv
import datetime
import logging
import urlparse

# AppEngine imports
from google.appengine.api import users
from google.appengine.api.labs import taskqueue
from google.appengine.ext import db

# Django imports
from django import forms
from django.utils import simplejson

# Local imports
import constants
import library
import models


def _read_chunk_lines(uploaded_file):
  """Splits the uploaded chunks into lines and return them as a contiguous set.

  Args:
    uploaded_file: Object of type UploadedFile. Use chunks() to get iterable
        of file contents.
  """
  remainder = ''
  count = 0
  for chunk in uploaded_file.chunks():
    count += 1
    lines = (remainder + chunk).splitlines(True)  # Preserves newlines.
    num_lines = len(lines)

    logging.info('Chunk %d, lines: %d' % (count, num_lines))
    for line in lines:
      num_lines -= 1
      if num_lines > 0:
        yield line
      else:
        remainder = line
  if remainder:
    yield remainder


_VIDEO_WIDTH = '600px'
_VIDEO_HEIGHT = '300px'


def create_video_page_if_not_exists(tags, title, video_uri, creator=None):
  """Creates a page to reference the specified video, if it does not exist.

  - Creates VideoModel, if it does not exist yet.
  - Locate TrunkModel of the same name
    - If doesn't exist, create new DocModel and TrunkModel
    - If it does exist, load the head doc and make sure specified video is
      listed. If not, add it to the content list.

  Args:
    tags: A list of tags when creating a new doc, e.g.,
        ['math', 'Calculus']
    title: The title for the page matches that of the video.
    video_uri: The video ID is extracted and a VideoModel added, if it does
        not already exist.
    creator: Optional creator; instance of users.User. If None, the currently
        logged in use will be used. Will fail if not logged in (guest).

  Returns:
    Returns (status, attributes) where:
      status is True if inserted, False otherwise.
      attributes is a string with (tage, title, video_id) for returning as
         feedback
  """
  creator = creator or users.get_current_user()
  parsed = urlparse.urlparse(video_uri)
  video_id = None
  if parsed:
    qdict = cgi.parse_qs(parsed.query)
    if 'v' in qdict:
      video_id = qdict['v'][0]  # parse_qs() returns list, so get first one.
  if not video_id:
    logging.info('Cannot identify video id from "%s"' % video_uri)
    return False, None
  attributes = ','.join([str(tags), title, video_id])

  video = models.VideoModel.insert(
      creator=creator,
      video_id=video_id,
      title=title,
      width=_VIDEO_WIDTH,
      height=_VIDEO_HEIGHT)

  # Locate document with same title.
  result = False
  query = models.TrunkModel.all()
  query.filter('title =', title)
  if query.count() == 0:  # Not found
    doc = models.DocModel.insert_with_new_key(creator=creator)
    doc.title = title
    doc.tags.extend([db.Category(tag) for tag in tags])
    doc.content.append(video.key())
    trunk = doc.placeInNewTrunk(creator=creator)
    result = True
  else:
    trunk = query.get()  # Get first one and look at contents
    try:
      doc = db.get(trunk.head)
    except db.BadKeyError:
      return False, attributes
    if isinstance(doc, models.DocModel):
      content_keys = set([str(k) for k in doc.content])
      if str(video.key()) not in content_keys:
        doc.content.append(video.key())
    else:
      logging.info(
          '**** Trunk found, but head is not a DocModel for "%s"' % title)
  return result, attributes


def import_videos(videos, creator=None):
  """Import a set of videos, creating a doc for each.

  Args:
    videos: A list of (tags, title, video_uri) tuples
    creator: Optional creator, instance of users.User.

  Returns:
    A list of summary lines, to be displayed for status purposes.
  """
  response = []
  success = 0
  for tags, title, video_uri in videos:
    status, attributes = create_video_page_if_not_exists(
        tags, title, video_uri, creator=creator)
    if status:
      success += 1
    response.append(attributes)
  response.append('%d / %d inserted' % (success, len(videos)))
  return response


def handle_khan_math_videos(uploaded_file, start_index, batch_size):
  """Handle bulk upload of math videos.

  Expected to be a CSV with the first three columns:

    tag,title,uri

  For each line, this handler creates a new page, if it does not exist
  already.  The video ID must be extracted from the URI and 'math' should
  be added to the labels.

  Args:
    uploaded_file: Object of type UploadedFile. Use chunks() to get iterable
        of file contents.
    start_index: Index at which to start importing. If None, uses 0.
    batch_size: If None, import all at once.
  """
  reader = csv.reader(_read_chunk_lines(uploaded_file))
  videos = []
  for record in reader:
    if reader.line_num == 1:
      continue  # Skip header
    tag, title, video_uri = record[0:3]
    if video_uri and title:
      videos.append((['math', tag], title, video_uri))

  response = []
  count = len(videos)

  # Batch process the videos, pushing them to a task queue.
  start = start_index or 0
  batch_size = batch_size or count

  response = import_videos(videos[start:start + batch_size])
  start += batch_size

  # Queue remaining videos on the task queue.
  creator_id = users.get_current_user().user_id()
  while start < count - 1:
    payload = {
        'creator_id': creator_id,
        'videos': videos[start:start + batch_size],
        }
    start += batch_size
    payload_json = simplejson.dumps(payload)
    taskqueue.add(url='/task/importVideos', payload=payload_json,
                  countdown=5)

  if count > batch_size:
    response.append('Placed remaining %d on TaskQueue' % (count - batch_size))
  return '<br>'.join(response)


# Maps content type to a handler
#
# The arguments to the handler must be:
#   file object, start_index, batch_size
_HANDLER_MAP = {
    'khan_math_videos': handle_khan_math_videos,
}


def handle_uploaded_file(form_dict, uploaded_file):
  """Main entry point for handling file.

  Args:
    form_dict: The dictionary of form fields.
      content_type is the value of the content-type selector
      start is the starting index from which import
      batch_size is the number of entries to load at a time.
    uploaded_file: Object of type UploadedFile. Use chunks() to get iterable
        of file contents.
  """
  content_type = form_dict['content_type']
  logging.info('Uploading %s' % content_type)
  handler = _HANDLER_MAP.get(content_type)
  if handler:
    result = handler(
        uploaded_file, form_dict['start_index'], form_dict['batch_size'])
  else:
    result = 'Did not find handler for type: %s', content_type
    logging.error(result)
  return result
