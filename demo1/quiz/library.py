# Copyright 2008 Google Inc.
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

"""Library for quiz module."""

import cgi
import logging
import base64
import string
import random
import os

from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import db

import django.template
# import django.utils.safestring
from django.utils import simplejson
from django.core.urlresolvers import reverse

import quiz.models as models

# For registering filter and tag libs.
register = django.template.Library()

	
@register.filter
def class_name(cls):
  """Returns name of the class."""
  return cls.__class__.__name__


@register.filter
def get_key(cls):
  """Returns key for an object if it exists in datastore."""
  try:
    object_key = cls.key()
  except db.NotSavedError:
    return None
  return str(object_key)


### Library function to interact with datastore ###

def gen_random_string(num_chars=16):
  """Generates a random string of the specified number of characters.

  First char is chosen from set of alphabets as app engine requires
  key name to start with an alphabet. Also '-_' are used instead of
  '+/' for 64 bit encoding.

  Args:
    num_chars: Length of random string.
  Returns:
    Random string of length = num_chars
  """
  # Uses base64 encoding, which has roughly 4/3 size of underlying data.
  first_letter = random.choice(string.letters)
  num_chars -= 1
  num_bytes = ((num_chars + 3) / 4) * 3
  random_byte = os.urandom(num_bytes)
  random_str = base64.b64encode(random_byte, altchars='-_')
  return first_letter+random_str[:num_chars]


def create_temp_session_id():
  """Creates a new random session id for temporary session.
  
  NOTE(mukundjha): All session id should be prefixed with its type.
    There can be two types of session temp or user, temp is when 
    no user information is available or the quiz is not embedded 
    inside a doc.

  Returns:
    A unique session id (string).

  TODO(mukundjha): Decide id length.
  TODO(mukundjha): To incorporate temp ids, currently this is not used.
  """
  while True:
    session_id = 'temp' + gen_random_string()
    session_count = models.ResponseModel.all().filter(
        'session_id =', session_id).count()
    if not session_count:
      return session_id
    else: 
      logging.info('Clash while creating session id %s', session_id)


def insert_with_new_key(cls, parent=None, **kwargs):
  """Insert model into datastore with a random key.

  Args:
    cls: Data model class (ex. models.DocModel).
    parent: optional parent argument to bind models in same entity group.
      NOTE: If parent argument is passed, key_name may not be unique across
      all entities.
  Returns:
    Data model entity or None if error.

  TODO(mukundjha): Check for race condition.
  """
  while True:
    key_name = gen_random_string()
    entity = cls.get_by_key_name(key_name, parent=parent)
    if entity is None:
      entity = cls(key_name=key_name, parent=parent, **kwargs)
      entity.put()
      break
    else:
      logging.info("Entity with key "+key_name+" exists")
  return entity


def create_quiz_property(**kwargs):
  """Creates a new instance of quiz property in datastore.
  
  Returns:
    QuizPropertyModel object.
  """ 
  quiz_property = insert_with_new_key(models.QuizPropertyModel, **kwargs);
  return quiz_property


def create_quiz(**kwargs):
  """Inserts a new quiz into the database.

  Returns:
    QuizModel object.
  """
  quiz = insert_with_new_key(models.QuizModel, **kwargs)  
  quiz_id = str(quiz.key())
  quiz_trunk = db.run_in_transaction(create_new_trunk_with_quiz,
                                     quiz_id, **kwargs)
  quiz.trunk = quiz_trunk
  quiz.put()
  return quiz


def add_question(quiz, question):
  """Adds a question object to the quiz if not already added.
  
  Args:
    quiz: Quiz to which question needs to be added.
    question: Question to be added.
  """
  query = models.QuizQuestionListModel.all().filter(
    'question =', question).filter('quiz =', quiz)
  
  if not query.count:
    insert_with_new_key(models.QuizQuestionListModel, quiz=quiz,
                        question=question)


def create_question(quiz, **kwargs):
  """Inserts a new question into the quiz.

  Args:
    quiz: Quiz object to associate question with.
  Returns:
    QuestionModel object.
  """
  question = insert_with_new_key(models.QuestionModel, **kwargs)
  insert_with_new_key(models.QuizQuestionListModel, quiz=quiz,
      question=question)
  return question


def create_choice(**kwargs):
  """Creates a new choice object.
 
  Returns:
    ChoiceModel object.
  """
  choice = insert_with_new_key(models.ChoiceModel, **kwargs)
  return choice


def store_response(session_id, quiz_id, question_id,
                   answered_correctly, attempts):
  """Stores user response in the datastore.

  Args:
    session_id: Session Identifier.
    quiz_id: Key for associated quiz.
    answered_correctly: True if answer was correct.
    attempts: Number of attempts so far.
  """
  try:
    quiz = db.get(quiz_id)
  except db.BadKeyError:
    logging.error('Incorrect key passed for quiz %s', quiz_id)
  try:
    question = db.get(question_id)
  except db.BadKeyError:
    logging.error('Incorrect key passed for question %s', question_id)
  entry = models.ResponseModel.all().filter('session_id =', session_id).filter(
      'quiz =', quiz).filter('question =', question).get()
  if not entry: 
    insert_with_new_key(models.ResponseModel, session_id=session_id, quiz=quiz,
        question=question, answered_correctly=answered_correctly,
        quiz_trunk=quiz.trunk, attempts=attempts)
  else:
    entry.answered_correctly = answered_correctly
    entry.attempts = attempts
    entry.put()


def reset_quiz(session_id, quiz):
  """Resets all entries for quiz in collected response.
  Useful for resetting entries when questions repeat.
  
  Args:
   session_id: Id passed by parent Lantern doc, mapping the user.
   quiz_id: Id for the associated quiz.
  """
  score_entry = models.QuizScoreModel.all().filter(
      'session_id =', session_id).filter('quiz =', quiz).get()
  if score_entry:
    score_entry.score = 0.0
    score_entry.progress = 0.0
    score_entry.questions_attempted = 0
    score_entry.put()

  reset_responses(session_id, quiz)


def reset_responses(session_id, quiz):
  """Resets all response entries for quiz in collected response.
  Useful for resetting entries when questions repeat.
  
  Args:
   session_id: Id passed by parent Lantern doc, mapping the user.
   quiz_id: Id for the associated quiz.
  """
  response_entries = models.ResponseModel.all().filter(
      'session_id =', session_id).filter('quiz =', quiz)

  for entry in response_entries:
    entry.answered_correctly = False
    entry.attempts = 0
    entry.put() 

 
def pick_next_question(session_id, quiz, repeat):
  """Selects the next question to be presented.

  TODO(mukundjha): Decide if the data required for selection should
  come from doc or from quiz database. Currently we use the data stored
  in the datastore per-session for producing next question.
  
  Args:
    session_id: Id passed by parent Lantern doc, mapping the user.
    quiz_id: Id for the associated quiz.
    repeat: If true questions keep recycling even after user has seen all
      of them.

  Returns:
    Question object if there exists a valid question, else None.
  """
  #quiz = db.get(quiz_id)
  all_questions = models.QuizQuestionListModel.all().filter('quiz =', quiz)
  if not all_questions.count():
    return None
  
  all_ques = set([entry.question.key() for entry in all_questions])
  
  answered_correctly = models.ResponseModel.all().filter(
      'session_id =', session_id).filter('quiz =', quiz).filter(
      'answered_correctly =', True)
  
  answered = set([response.question.key() for response in answered_correctly])
  
  if answered:
    allowed_questions = all_ques.difference(answered)
  else:
    allowed_questions = all_ques
 
  if not allowed_questions and not repeat:
    return None

  elif not allowed_questions:
    reset_responses(session_id, quiz)
    allowed_questions = all_ques

  logging.info('Allowed Questions: %r', allowed_questions)
  question_key = random.choice(list(allowed_questions))

  question = db.get(question_key)
  logging.info('picked question: %r', question_key)
  return question


def check_answer(question_id, choice_id):
  """Checks if the answer provided is correct or not.

  TODO(mukundjha): Check if choice belongs to same question.
  """
  try: 
    choice = db.get(choice_id)
  except db.BadKeyError:
    logging.error('Error the choice key entered in check_answer is invalid %s',
                   choice_id)
    return None
  
  if choice.is_correct:
    return True
  else:
    return False


def increment_score(session_id, quiz, question, attempts):
  """Increments score associated with a quiz and a session.
   
  Scoring: Score for a quiz is always normalized to be out of 100 points. 
  Based on number of maximum allowed questions (set in the quiz property) 
  for the quiz, each question is given equal weightage.

  For each question user is allowed upto num_of_choices-1 tries. For each 
  wrong attempt user loses certain amount of points. Currently user loses 
  equal amount for each attempt.

  For example: If the database for the quiz has 10 questions. Each question
  carry 10 points. Suppose one of the question has 5 choices, then user is 
  allowed 4 attempts, (taking a hint or selecting/eleminating a choice is 
  considered as an attempt). Each wrong attempt user loses 10/4 = 2.5 points.
 
  There is also a notion of completion status, which records percentage of 
  question attempted and is use to track if user is complete with the module.
  
  Args: 
   session_id : Id associated with current user.
   quiz: Associated quiz.
   question: Question being attempted.
   attempts: No of attempts so far including the current one.

  Returns:
    An updated tuple of (score, progress) describing current status of the 
    quiz for the given session.
  """
  total_questions = models.QuizQuestionListModel.all().filter(
      'quiz =', quiz).count()
  min_questions = quiz.quiz_property.min_questions
  
  if min_questions != 0 and total_questions > min_questions:
    total_questions = min_questions

  if not total_questions:
    return (0, 0)

  quanta = 100.0/total_questions

  total_choices = len(question.choices)
  
  if total_choices >= 2:
    loss = quanta / (total_choices - 1)
  else:
    return
  
  points = quanta - (loss * (attempts - 1))
  score_entry = models.QuizScoreModel.all().filter(
      'session_id =', session_id).filter('quiz =', quiz).get()

  if score_entry:
    if score_entry.questions_attempted < total_questions:
      score_entry.score += points
      score_entry.questions_attempted += 1
      score_entry.progress = (
          score_entry.questions_attempted * 100.0 / total_questions)
    else:
      score_entry.progress = 100.0
    
    score_entry.put()
    return (score_entry.score, score_entry.progress)

  else:
    # this is the first correctly answered question
    progress = (1 * 100.0) / total_questions
    insert_with_new_key(models.QuizScoreModel, session_id=session_id,
                        quiz=quiz, score=points, questions_attempted=1,
                        quiz_trunk=quiz.trunk, progress=progress)
  return (points, progress)


def create_new_trunk_with_quiz(quiz_id, **kwargs):
  """Creates a new trunk with given quiz as head.

  WARNING: Since we are passing parent parameter in insert_with_new_key,
  function will only check for uniqueness of key among entities having 'trunk'
  as an ancestor. This no longer guarantees unique key_name across all 
  entities.

  NOTE(mukundjha): No check is done on quiz_id, it's responsibility of
  other functions calling create_new_trunk_with_quiz to check the parameter
  before its passed.

  Args:
    quiz_id: String value of key of the document to be added.
  Returns:
    Returns created quiz trunk.
  Raises:
    InvalidQuizError: If the quiz_id is invalid.
  """
  quiz_trunk = insert_with_new_key(models.QuizTrunkModel)

  message = kwargs.pop('commit_message', 'Commited a new revision')
  quiz_revision = insert_with_new_key(models.QuizRevisionModel, parent=quiz_trunk,
    quiz_id=quiz_id, commit_message=message)

  quiz_trunk.head = quiz_id
  quiz_trunk.put()
  return quiz_trunk


def append_to_trunk(quiz_trunk_id, quiz_id, **kwargs):
  """Appends a quiz to end of the trunk.

  NOTE(mukundjha): No check is done on quiz_id, it's responsibility of
  other functions calling append_to_trunk to check the parameter
  before its passed.

  Args:
    quiz_trunk_id: Key of the quiz trunk.
    quiz_id: String value of key of the quiz to be added.
  Returns:
    Returns modified trunk.
  Raises:
    InvalidQuizError: If the quiz_id is invalid.
    InvalidQuizTrunkError: If the quiz_trunk_id is invalid.
  """
  try:
    quiz_trunk = db.get(quiz_trunk_id)
  except db.BadKeyError, e:
    raise models.InvalidTrunkError('Quiz Trunk is not valid %s',
      trunk_id)

  message = kwargs.pop('commit_message', 'Commited a new revision')
  quiz_revision = insert_with_new_key(
      models.QuizRevisionModel, parent=quiz_trunk, quiz_id=quiz_id,
      commit_message=message) 

  quiz_trunk.head = quiz_id
  quiz_trunk.put()
  return quiz_trunk


def get_quiz_from_trunk(session_id, quiz_trunk_id):
  """Retrieves relevant quiz version based on user's response history.

  Returns the last version i.e., head of the trunk.
  
  Args:
    session_id: String representing session_id.
    quiz_trunk_id: trunk_id representing the quiz.

  Returns:
    Quiz object.
  """
  try:
    quiz_trunk = db.get(quiz_trunk_id)
  except db.BadKeyError:
    return None
    
  last_response_entry = models.ResponseModel.all().filter(
        'session_id =', session_id).filter('quiz_trunk =', quiz_trunk).order(
        '-time_stamp').get()

  if last_response_entry:
    return last_response_entry.quiz

  else:
    try:
      quiz = db.get(quiz_trunk.head)
    except db.BadKeyError:
      return None
    return quiz


def fetch_new_question_and_status(session_id, quiz_trunk_id, repeat):
  """Fetches new question and current status to be presented based on 
  session's history.

  If repeat argument is True, function keeps recycling questions 
  even if user is finished with all the questions.

  Args:
    session_id: String ID for user.
    quiz_trunk_id: Id of the trunk associated with the quiz.
    repeat: Flag to repeat questions even if user has answered all.

  Returns: 
    Returns a dict object with fetched question and current status. Question is
    set to None if there are no questions to be fetched. 

  TODO(mukundjha): We can absorb get_quiz_from_trunk to reduce number of 
    calls to datastore.
  """
  quiz = get_quiz_from_trunk(session_id, quiz_trunk_id)
  
  # for picking the correct quiz version
  
  last_response_entry = models.ResponseModel.all().filter(
      'session_id =', session_id).filter('quiz =', quiz).order(
      '-time_stamp').get()
  
  if last_response_entry and last_response_entry.answered_correctly == False:
    question = last_response_entry.question
    attempts = last_response_entry.attempts
  
  else: 
    question = pick_next_question(session_id, quiz, repeat)
    attempts = 0

  score_entry = models.QuizScoreModel.all().filter(
      'session_id =', session_id).filter('quiz =', quiz).get()

  if not score_entry:
    score = 0
    progress = 0
  else:
    score = round(score_entry.score)
    progress = round(score_entry.progress)
  
  return {'current_status' : {'score' : score, 'progress': progress},
          'question' : question, 'attempts': attempts, 'title': quiz.title}

def remove_question_from_quiz(question, quiz):
  """Removes question from the quiz.
  """
  question_entry = models.QuizQuestionListModel.all().filter(
      'question =', question).filter('quiz =',quiz).get()
  if question_entry:
    db.delete(question_entry)


def question_to_json(question_and_status_dict, repeat):
  """Converts question dict into JSON object, also attaches other relevant
  messages.

  If repeat argument is True, function keeps recycling questions 
  even if user is finished with all the questions.

  Args:
    question_and_status_dict: Dict object representing question to 
      be presented and current status of the quiz.
    repeat: Flag to repeat questions even if user has answered all.

  Returns: 
    Returns JSON object to be presented.
  """
  question = question_and_status_dict['question'] 
  # gen_message = general message
  if not question and not repeat:
    gen_message = 'Congratulations you have completed the quiz'
    question_dict = {
        'body': 'You have completed the quiz!! Please move to the next one!',
        'choices':[],
        'reset': True}

  elif not question:
    gen_message = 'This quiz is empty.'
    question_dict = {
        'body': 'This quiz is empty!',
         'choices':[]}
  else:
    question_dict = question.dump_to_dict()
    gen_message = None
  data_dict = {'current_status' : question_and_status_dict['current_status'],
               'question' : question_dict,
               'attempts': question_and_status_dict['attempts'],
               'gen_message': gen_message,
               'title': question_and_status_dict['title']}

  return simplejson.dumps(data_dict)
