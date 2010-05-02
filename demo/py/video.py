# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Demo video page for khan edu site.
#
# Query parameters:
#  f: Field, e.g., math, science, etc.
#  s: Subject, e.g., algebra, ca-geometry
#  v: Video id, e.g., bAerID24QJ0

import os

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

# Packages for this application
from py import base
from py import constants

# Substitute for a real DB
_SUBJECT_MAP = {
  ('math', 'arithmetic'): 'Arithmetic',
  ('math', 'prealgebra'): 'Pre-algebra',
  ('math', 'algebra'): 'Algebra',
  ('math', 'ca-algebra1'): 'California Standards Test: Algegra I',
  ('math', 'ca-algebra2'): 'California Standards Test: Algegra II',
  ('math', 'geometry'): 'Geometry',
  ('math', 'ca-geometry'): 'California Standards Test: Geometry',
  ('math', 'trigonometry'): 'Trigonometry',
  ('math', 'precalculus'): 'Pre-calculus',
  ('math', 'calculus'): 'Calculus',
  ('math', 'statistics'): 'Statistics',
  }

_DEFAULT_VIDEO_ID = 'bAerID24QJ0';

# Video Map
_ALGEBRA_COURSE_MAP = {
  'bAerID24QJ0':
      ('Algebra: Linear Equations 1', 'Equations of the form AX=B'),
  'DopnmxeM5-s':
      ('Algebra: Linear Equations 2', 'Solving equations of the form AX+B=C'),
  'Zn-GbH2S0Dk':
      ('Algebra: Linear Equations 3',
       'Linear equations with multiple variable and constant terms'),
  '9IU#k9fn2Vs':
      ('Algebra: Linear Equations 4',
       'Solving linear equations with variable expressions in the denominators '
       'of fractions'),
  'VgDe_D8ojxw':
      ('Algebra: Solving Inequalities', 'Solving linear inequalities'),
  '2UrcUfBizyw':
      ('Algebra: Graphing lines 1', 'Graphing linear equations'),
  'Nhn-anmubYU':
      ('Algebra: Slope and Y-intercept intuition',
       'Getting a feel for slope and y-intercept'),
  'hXP1Gv9IMBo':
      ('Algebra: Slope', 'Figuring out the slope of a line'),
  'Kk9IDameJXk':
      ('Algebra: Slope 2', 'Second part of determining the slope of a line'),
  '8XffLj2zvf4':
      ('Algebra: Slope 3', 'Part 3 of slope'),
  }

_ALGEBRA_COURSE_LIST = [
  'bAerID24QJ0',
  'DopnmxeM5-s',
  'Zn-GbH2S0Dk',
  '9IU#k9fn2Vs',
  'VgDe_D8ojxw',
  '2UrcUfBizyw',
  'Nhn-anmubYU',
  'hXP1Gv9IMBo',
  'Kk9IDameJXk',
  '8XffLj2zvf4',
  ]

_VIDEO_MAP = {
  ('math', 'algebra'): (_ALGEBRA_COURSE_LIST, _ALGEBRA_COURSE_MAP),
  }

class Video(base.BaseHandler):
  _MAIN_MENU = """
  <a href="http://www.khanacademy.org">Video Library</a> |
  <a href="http://www.youtube.com/watch?v=%s&amp;feature=youtube_gdata">Rate and Comment on YouTube</a> |
  <a href="/">Exercises (Requires Login)</a>
  """
  def get(self):
    query_vars = self.request.queryvars
    subject_key = (query_vars.get('f'), query_vars.get('s'))

    course_list, course_map = _VIDEO_MAP.get(subject_key, ([], []))
    video_id = query_vars.get('v')
    if video_id:
      course_topic = course_map.get(video_id, ('Unknown', 'Unknown'))
      subject = course_topic[0]
    else:
      course_topic = ('', '')
      subject = _SUBJECT_MAP.get(subject_key, 'Missing Subject')

    template_values, template_path = self.GetBaseTemplateValues(
      subject, 'video.html')
    template_values['mainmenu'] = self._MAIN_MENU % video_id

    template_values['field'] = subject_key[0]
    template_values['subject'] = subject_key[1]
    template_values['video_id'] = video_id
    template_values['course_topic'] = course_topic

    template_values['course_list'] = course_list

    if video_id:
      template_values['course_topic'] = course_map.get(video_id,
                                                       ('Unknown', 'Unknown'))
      try:
        index = course_list.index(video_id)
        if index > 0:
          video_prev = course_list[index - 1]
          template_values['video_prev'] = video_prev
          template_values['topic_prev'] = course_map.get(video_prev)[0]
        if index < len(course_list) - 1:
          video_next = course_list[index + 1]
          template_values['video_next'] = video_next
          template_values['topic_next'] = course_map.get(video_next)[0]
      except ValueError:
        pass

    user_progress = self._GetUserProgress(template_values['user'], course_list)
    n_complete = len(user_progress)
    template_values['n_complete'] = n_complete
    template_values['n_incomplete'] = len(course_map) - n_complete

    course_rows = self._BuildCourseList(course_list, course_map,
                                        user_progress, 3)
    template_values['course_rows'] = course_rows

    self.response.out.write(template.render(template_path, template_values))

  def _GetUserProgress(self, user, course_list):
    """Returns a map of user progress for the course list. MOCK. """
    progress_map = {}
    for idx, course_id in enumerate(course_list):
      if idx < 3:
        progress_map[course_id] = True
    return progress_map

  def _BuildCourseList(self, course_list, course_map, user_progress, ncols):
    """Builds a list rows entries for the tabular view.

    Args:
      course_list: List of topic IDs.
      course_map: A map of topic tuples: (title, description)l
      user_progress: Map of topics completed by the user, keyed by topic ID.
      ncols: Number of columns per row.

    Returns:
      A list of list of tuples.
        - First level list is rows
        - Next level is columns
        - Tuple is (index, id, title, description)
    """
    rows = []
    for idx, id in enumerate(course_list):
      if idx % ncols == 0:
        cols = []
        rows.append(cols)
      title, desc = course_map.get(id, ('', ''))
      cols.append((idx + 1, id, title, desc, user_progress.get(id, False)))
    return rows

application = webapp.WSGIApplication(
  [('/video', Video),
   ],
  debug=True)


def main():
  run_wsgi_app(application)

if __name__ == '__main__':
  main()
