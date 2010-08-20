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
#

"""Views for quiz module."""

import cgi
import itertools
import os
import logging
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from django.utils import simplejson
# Local imports.
import quiz.library as library
import quiz.models as models

 
class PresentQuiz(webapp.RequestHandler):
  """Presents quiz to a user."""

  def get(self):
    quiz_trunk_id = self.request.get('quiz_trunk_id')
    quiz_id = self.request.get('quiz_id')
    try:
      quiz = db.get(quiz_id) 
    except:
      self.response.out.write('Problem with quiz id '+ str(quiz_id));
      return
    path = os.path.join(os.path.dirname(__file__), 'template/quiz.html')
    self.response.out.write(template.render(path,
                            {'quiz_trunk_id': quiz_trunk_id,
                            'quiz_id': quiz_id,
                            'title': quiz.title}))


class GetQuestionAjax(webapp.RequestHandler):
  """Sends back a new quiz object and score for current session."""

  def get(self):
    session_id = self.request.get('session_id')
    quiz_trunk_id = self.request.get('quiz_trunk_id')
    question_and_status_dict = library.fetch_new_question_and_status(
        session_id, quiz_trunk_id, True)
    json_result = library.question_to_json(question_and_status_dict,
                                          True)
    self.response.out.write(json_result)
  

class ResetQuizAjax(webapp.RequestHandler):
  """Resets the quiz score asscociated with the session and sends back 
  a new question and score for current session."""

  def get(self):
    session_id = self.request.get('session_id')
    quiz_trunk_id = self.request.get('quiz_trunk_id')
    quiz = library.get_quiz_from_trunk(session_id, quiz_trunk_id)
    library.reset_quiz(session_id, quiz)
    question_and_status_dict = library.fetch_new_question_and_status(
        session_id, quiz_trunk_id, True)
    json_result = library.question_to_json(question_and_status_dict,
                                          True)
    self.response.out.write(json_result)


class CollectResponseAjax(webapp.RequestHandler):
  """Evaluates response and sends back a new quiz object, correct answer 
  and score for current session.

  TODO(mukundjha): Check against passing invalid question.
  TODO(mukundjha): Check against BadKeyError.
  """

  def get(self):
    session_id = self.request.get('session_id')
    quiz_id = self.request.get('quiz_id')
    quiz_trunk_id = self.request.get('quiz_trunk_id')
    question_id = self.request.get('question_id')
    answer_id = self.request.get('answer')
    attempts = int(self.request.get('attempts'))
    check_response = library.check_answer(question_id, answer_id);
    data_dict = {}

    # fetches quiz based on user's history
    quiz = library.get_quiz_from_trunk(session_id, quiz_trunk_id)
    if not quiz:
      error_msg = 'Error loading quiz from trunk %s' % quiz_trunk_id
      self.response.out.write(simplejson.dumps({'error_msg' : error_msg}))
      return

    # required for storing response
    quiz_id = str(quiz.key())

    # invalid response
    if check_response is None:
      error_msg = 'Invalid response'
      self.response.out.write(simplejson.dumps({'error_msg' : error_msg}))
      return

    # correct response
    elif check_response:
      choice = db.get(answer_id)
      message = 'Correct!!\n %s ' % choice.message
      library.store_response(session_id, quiz_id, question_id, True, attempts)
      try:
        question = db.get(question_id)
      except db.BadKeyError:
        error_msg = 'Error fetching question:<br> Question key is not correct'
        self.response.out.write(simplejson.dumps({'error_msg' : error_msg}))
        return

      score, progress = library.increment_score(
          session_id, quiz, question, attempts)

      data_dict['current_status'] = {'score': round(score),
                                     'progress': round(progress)}
      data_dict['accepted'] = True

    else:
      choice = db.get(answer_id)
      message = 'Wrong!!\n %s' % choice.message
      library.store_response(session_id, quiz_id, question_id, False, attempts)
      data_dict['accepted'] = False

    data_dict['message'] = message
    
    logging.info('**********Response JSON ********* %r',
                  simplejson.dumps(data_dict))
    self.response.out.write(simplejson.dumps(data_dict))


class EditQuiz(webapp.RequestHandler):
  """Edit interface for a given quiz."""
  
  def get(self):
    quiz_id = self.request.get('quiz_id')
    try:
      quiz = db.get(quiz_id)
    except db.BadKeyError:
      self.response.write('Error the quiz id is not valid.')

    query = models.QuizQuestionListModel.all().filter(
        'quiz =', quiz).order('-time_stamp')

    list_of_questions = [entry.question for entry in query]

    path = os.path.join(os.path.dirname(__file__), 'template/editQuiz.html')
    self.response.out.write(template.render(path,
                           {'quiz' : quiz, 'questions': list_of_questions}))
 
class SubmitNewQuiz(webapp.RequestHandler):
  """Creates a new quiz.
  
  TODO(mukundjha): Account for different property settings.
    Currently works only for default property.
  """

  def post(self):
    quiz_id = self.request.get('quiz_id')
    
    title  = self.request.get('quiz_title')
    level = int(self.request.get('quiz_level', 7))
    if quiz_id:
      try:
        quiz = db.get(quiz_id)
      except db.BadKeyError:
        self.response.write('BadKeyError: wrong key for quiz, %s',
                             quiz_id)
      quiz.title = title
      quiz.level = level
      quiz.put()

    else:
      quiz_property = library.create_quiz_property()
      quiz = library.create_quiz(title=title, difficulty_level=level,
                               quiz_property=quiz_property)
    if quiz_id:
      redirection_url = '/quiz/viewQuiz?quiz_id=%s' % quiz.key()
    else:
      redirection_url = '/quiz/addQuestion?quiz_id=%s' % quiz.key()
    self.redirect(redirection_url)


class DeleteQuestion(webapp.RequestHandler):
  """Adds a new question to a the quiz.
  """

  def post(self):
    question_id  = self.request.get('question_id')
    quiz_id  = self.request.get('quiz_id')

    try:
      quiz = db.get(quiz_id)
    except db.BadKeyError:
      self.response.write('BadKeyError: wrong key for quiz, %s',
                           quiz_id)

    if question_id:
      try:
        question = db.get(question_id)
      except db.BadKeyError:
        self.response.write('BadKeyError while adding question');
    library.remove_question_from_quiz(question, quiz)
    self.redirect('/quiz/editQuiz?quiz_id='+quiz_id)


class SubmitNewQuestion(webapp.RequestHandler):
  """Adds a new question to a the quiz.
  """

  def post(self):
    question_id  = self.request.get('question_id')
    quiz_id  = self.request.get('quiz_id')

    try:
      quiz = db.get(quiz_id)
    except db.BadKeyError:
      self.response.write('BadKeyError: wrong key for quiz, %s',
                           quiz_id)

    if question_id:
      try:
        question = db.get(question_id)
      except db.BadKeyError:
        self.response.out.write('BadKeyError while adding question');
      library.remove_question_from_quiz(question, quiz)

    shuffle = self.request.get('choice_shuffle', False)
    question_text = self.request.get('question_text')
    hints = self.request.get_all('question_hints')
    choice_texts = self.request.get_all('choice_texts')
    choice_messages = self.request.get_all('choice_messages')
    correct_choice = int(self.request.get('is_correct', 0))

    if not correct_choice:
      self.response.write('None of the answer is marked to be correct!')
      return

    choice_is_correct_vals = []
    for i in range(0, len(choice_texts)):
      if i == correct_choice-1:
        choice_is_correct_vals.append(True)
      else:
        choice_is_correct_vals.append(False)

    choice_list = []
    for ch_text, ch_msg, ch_is_correct in itertools.izip(
        choice_texts, choice_messages, choice_is_correct_vals ):

      new_choice = library.create_choice(body=ch_text, message=ch_msg,
                                         is_correct=ch_is_correct)
      choice_list.append(new_choice.key())

    library.create_question(quiz, body=question_text, hints=hints,
                            choices=choice_list, shuffle_choices=shuffle); 
    if question_id:
      redirection_url = '/quiz/editQuiz?quiz_id=%s' % quiz.key()
    else:   
      redirection_url = '/quiz/addQuestion?quiz_id=%s' % quiz.key()
    self.redirect(redirection_url)


class CreateQuiz(webapp.RequestHandler):
  """Presents an edit page for adding a quiz.
  """

  def get(self):
    path = os.path.join(os.path.dirname(__file__), 'template/createQuiz.html')
    self.response.out.write(template.render(path,
                           {}))


class AddQuestion(webapp.RequestHandler):
  """Presents an edit page for adding questions.
  TODO(mukundjha): Use filters instead of passing key to the template.
  """

  def get(self):
    quiz_id = self.request.get('quiz_id')
    try:
      quiz = db.get(quiz_id)
    except db.BadKeyError:
      self.response.write('Error the quiz id is not valid.')

    path = os.path.join(os.path.dirname(__file__), 'template/addQuestion.html')
    self.response.out.write(template.render(path,
                           {'quiz' : quiz,
                            'quiz_key' : quiz.key()}))


class EditQuestion(webapp.RequestHandler):
  """Presents an edit page for editing questions.
  TODO(mukundjha): Use filters instead of passing key to the template.
  """

  def get(self):
    quiz_id = self.request.get('quiz_id')
    question_id = self.request.get('question_id')
    logging.info('\n ****** Question : %r\n', question_id)
    try:
      quiz = db.get(quiz_id)
    except db.BadKeyError:
      self.response.write('Error the quiz id is not valid.')
    try:
      question = db.get(question_id)
    except db.BadKeyError:
      self.response.write('Error the question is not valid.')
    choices = [];
    for ch in question.choices:
      choices.append(db.get(ch))
#    logging.info('\n ****** Question : %r\n', question.choices[0].body)
    path = os.path.join(os.path.dirname(__file__), 'template/editQuestion.html')
    self.response.out.write(template.render(path,
                           {'quiz' : quiz,
                            'quiz_key' : quiz.key(),
                            'question': question,
                            'choices': choices}))

  

class ViewQuiz(webapp.RequestHandler):
  """Returns a page with list of questions in the quiz."""

  def get(self):
    quiz_id = self.request.get('quiz_id')
    try:
      quiz = db.get(quiz_id)
    except db.BadKeyError:
      self.response.write('Error the quiz id is not valid.')
    
    query = models.QuizQuestionListModel.all().filter(
        'quiz =', quiz).order('-time_stamp')
    
    list_of_questions = [entry.question for entry in query]
    
    path = os.path.join(os.path.dirname(__file__), 'template/viewQuiz.html')
    self.response.out.write(template.render(path,
                           {'quiz' : quiz, 'questions': list_of_questions}))


class SendWidgetList(webapp.RequestHandler):
  """Sends a list of quizes available and other widgets.

  TODO(mukundjha): Move this to lantern and replace with 
    widget registration.
  """
  def get(self):
    quiz_list = models.QuizModel.all().fetch(50)
    widget_list = []
    py_shell = {'title': 'Python Shell',
                'link': 'http://pythonshell1.appspot.com'}

    khan_exercise = {'title': 'Khan Academy- Basic Trigonometry',
        'link': 
            'http://tempkhanacadquiz.appspot.com/exercises?exid=trigonometry_1'}
    
    widget_list.append(py_shell)
    widget_list.append(khan_exercise)
    for quiz in quiz_list:
      quiz_entry = {'title': 'Lantern Quiz: '+ quiz.title, 
         'link': '/quiz?quiz_id=%s&quiz_trunk_id=%s' % (quiz.key(),
          quiz.trunk.key())}
      widget_list.append(quiz_entry)

    self.response.out.write(simplejson.dumps({'widget_list': widget_list}))

    
application = webapp.WSGIApplication(
    [('/quiz', PresentQuiz),
    ('/quiz/getQuestion', GetQuestionAjax),
    ('/quiz/collectResponse', CollectResponseAjax),
    ('/quiz/viewQuiz', ViewQuiz),
    ('/quiz/createQuiz', CreateQuiz),
    ('/quiz/addQuestion', AddQuestion),
    ('/quiz/submitQuestion',  SubmitNewQuestion),
    ('/quiz/resetQuiz',  ResetQuizAjax),
    ('/quiz/submitQuiz', SubmitNewQuiz),
    ('/quiz/editQuestion', EditQuestion),
    ('/quiz/widgetList', SendWidgetList),
    ('/quiz/editQuiz', EditQuiz)],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
