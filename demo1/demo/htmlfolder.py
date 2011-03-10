# Copyright 2011 Google Inc.
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

"""Fold part of HTML document source into reasonable length"""

import HTMLParser
from htmlentitydefs import codepoint2name
import re

class HTMLFolder(HTMLParser.HTMLParser):
  # Folding a long paragraph always at end of sentence tends to give
  # more predictable and stable result.  Match the payload with this
  # and replace all hits with ".\n"
  squash_eos_regsub = re.compile('\\.\s+').sub
  DEFAULT_LIMIT = 70

  def __init__(self, limit=0):
    HTMLParser.HTMLParser.__init__(self)
    self._limit = limit or HTMLFolder.DEFAULT_LIMIT
    self._buffer = []
    self._buffer_length = 0
    self._result = []
    self._no_fold = 0

  def quote_entity(self, s):
    """Quote HTML entity name, for use in text and attribute values."""
    r = []
    for c in s:
      if ord(c) in codepoint2name:
        r.append("&%s;" % codepoint2name[ord(c)])
      else:
        r.append(c)
    return "".join(r)

  def flush(self):
    """An output line is done"""
    self._result.append("".join(self._buffer))
    self._buffer = []
    self._buffer_length = 0

  def out(self, s):
    """output string s; no folding tricks allowed."""
    self._buffer.append(s)
    self._buffer_length += len(s)

  def out_fold(self, s):
    """output string s.

    This is allowed to insert a LF after it if the line gets too long.
    """
    self.out(s)
    if self._limit < self._buffer_length:
      self.do_flush_line()

  def out_continue(self, s):
    """output s but prefix with a SP if not at the beginning of the line.

    This is allowed to insert a LF after the string if the line gets too long.
    """
    if self._limit < self._buffer_length + len(s) + 1:
      self.do_flush_line()
      self.out(s)
    elif self._buffer_length == 0:
      self.out(s)
    else:
      self.out(" %s" % s)

  def do_flush_line(self):
    """Insert a LF."""
    self.out("\n")
    self.flush()

  def flush_line(self):
    """Insert a LF if the line is too long."""
    if self._limit <= self._buffer_length:
      self.do_flush_line()

  def flush_head(self):
    """Send all but the last incomplete line to the result"""
    if 0 < len(self._buffer):
      self._result.extend(self._buffer[:-1])
      self._buffer = [self._buffer[-1]]
      self._buffer_length = len(self._buffer[0])

  def do_lines(self, data):
    """Common helper to handle the body text and comment that can be wrapped
    """

    data = self.squash_eos_regsub(".\n", data)
    is_first_line = 1
    for line in data.split("\n"):
      if is_first_line == 0:
        self.do_flush_line()
      line = self.quote_entity(line)
      current_length = self._buffer_length
      line_length = len(line)
      while self._limit < current_length + line_length:
        prefix_length = self._limit - current_length
        if prefix_length < 0:
          self.do_flush_line()
          prefix_length, current_length = self._limit, 0

        # Try to find cut point from earlier part to make the
        # result fit within the limit
        ix = line.rfind(" ", 0, prefix_length)
        if ix < 0 and current_length != 0:
          # Otherwise give up and cut at the first cut-point
          ix = line.find(" ")
        if ix < 0:
          # No way to split this---give up.
          break
        # Give the first part out
        self.out(line[0:ix])
        self.do_flush_line()
        # Start the next line while eating the SP
        line = line[ix+1:]
        current_length = self._buffer_length
        line_length = len(line)
      self.out(line)
      is_first_line = 0

  def close(self):
    """Finish processing; return the wrapped text"""
    self.flush()
    result = "".join(self._result)
    HTMLParser.HTMLParser.close(self)
    return result

  def handle_starttag(self, tag, attrs):
    if tag in ('p', 'div') and 0 < self._buffer_length:
      self.do_flush_line()
    self.out_fold("<%s" % tag)
    for (key, value) in attrs:
      self.out_continue('%s="%s"' % (key, self.quote_entity(value)))
    self.flush_line()
    self.out(">")
    if tag == 'pre':
      self._no_fold = 1

  def handle_entityref(self, name):
    self.out("&%s;" % name)

  def handle_charref(self, name):
    self.out("&#%s;" % name)

  def handle_endtag(self, tag):
    self.out_fold("</%s" % tag)
    self.out(">")
    if tag == 'pre':
      self._no_fold = 0

  def handle_data(self, data):
    if self._no_fold == 1:
      self.out(data)
      self.flush_head()
    else:
      self.do_lines(data)

  def handle_comment(self, data):
    self.out_fold("<!--")
    self.do_lines(data)
    self.flush_line()
    self.out("-->")


def htmlfold(s, line_width=0):
  """Line-fold HTML document to fit within the line-width

  Args:
    s: input string
    line_width: number of columns to fold to (defaults to %s)
  """ % HTMLFolder.DEFAULT_LIMIT
  try:
    folder = HTMLFolder(line_width)
    folder.feed(s)
    return folder.close()
  except HMLParser.HTMLParseError:
    return s


if __name__ == '__main__':
  import sys
  pp = HTMLFolder()
  while 1:
    line = sys.stdin.readline()
    if line == "":
      break
    pp.feed(line)
  result = pp.close()
  print result
