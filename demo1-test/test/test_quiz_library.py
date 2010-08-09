# !/usr/bin/python
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

"""Tests for the Lantern library functions."""

# Python imports
import logging
import unittest
import os

# AppEngine imports
from google.appengine.ext import db
from google.appengine.api import users

# local imports
from quiz import library
from quiz import models
import settings


class CreateQuiz(unittest.TestCase):
  """Tests creation of a quiz.
  TODO(mukundjha): Create proper test cases.
  """
 
class StoreResponseTest(unittest.TestCase):
  """Tests for storing response for a session."""

  def testResponseUpdate(self):
    quiz_property = library.create_quiz_property()
    quiz = library.create_quiz(quiz_property=quiz_property, title='test',
                               difficulty_level=7)
    question = library.create_question(quiz, body='question1')
    stored_response = library.insert_with_new_key(
        models.ResponseModel, session_id='xx', quiz=quiz.key(),
        question=question.key(), answered_correctly=False,
        quiz_trunk=quiz.trunk)
    library.store_response('xx', quiz.key(), question.key(), True, 3)
    query = models.ResponseModel.all().filter('session_id =', 'xx').filter(
        'quiz =', quiz).filter('question =', question)
    self.assertEquals(query.count(), 1)
    self.assertEquals(query.get().answered_correctly, True)
    self.assertEquals(query.get().attempts, 3)
    logging.info("***********%r %r",query.get().quiz_trunk, quiz.trunk) 
    self.assertEquals(str(query.get().quiz_trunk.key()), str(quiz.trunk.key()))

  def testResponseCreate(self):
    quiz_property = library.create_quiz_property()
    quiz = library.create_quiz(quiz_property=quiz_property, title='test',
                               difficulty_level=7)
    question = library.create_question(quiz, body='question1')
    library.store_response('xx', quiz.key(), question.key(), False, 5)
    query = models.ResponseModel.all().filter('session_id =', 'xx').filter(
        'quiz =', quiz).filter('question =', question)
    self.assertEquals(1, query.count())
    self.assertEquals(False, query.get().answered_correctly)
    self.assertEquals(5, query.get().attempts)
    self.assertEquals(str(query.get().quiz_trunk.key()), str(quiz.trunk.key()))
    

class PickQuestionTest(unittest.TestCase):
  """Tests question selection function."""

  def testSelectionWithNoQuestion(self):
    quiz_property = library.create_quiz_property()
    quiz = library.create_quiz(quiz_property=quiz_property, title='test')
    
    picked_question = library.pick_next_question('myid', quiz.key(), True)
    self.assertEquals(None, picked_question)

  def testSelectionWithAllQuestionsCorrectlyAnsweredWithoutRepeat(self):
    
    quiz_property = library.create_quiz_property()
    quiz = library.create_quiz(quiz_property=quiz_property, title='test')
    for i in range(0, 5):
      question = library.create_question(quiz)
      library.store_response('myid', quiz.key(), question.key(), True, 3)

    picked_question = library.pick_next_question('myid', quiz.key(), False)
    self.assertEquals(None, picked_question)
    
  def testValidSelectionWithoutRepeat(self):
    question_set = []
    quiz_property = library.create_quiz_property()
    quiz = library.create_quiz(quiz_property=quiz_property, title='test')
    for i in range(0, 5):
      question = library.create_question(quiz)
      question_set.append(question.key())

    # making entry for 3 questions
    for i in range(0,3):
      library.store_response('myid', quiz.key(), question_set[i], True, 3)

    # should we repeat to check for randomess?
    for index in range(0,10):
      picked_question = library.pick_next_question('myid', quiz.key(), False)
    
    # making set of 2 possible questions
      possible_set = set([ str(question_set[i]) for i in (3,4)])
      self.assertEquals(True, (str(picked_question.key()) in possible_set))

  def testValidWithNoAnsweredQuestionWithoutRepeat(self):
    question_set = []
    quiz_property = library.create_quiz_property()
    quiz = library.create_quiz(quiz_property=quiz_property, title='test')
    for i in range(0, 5):
      question = library.create_question(quiz)
      question_set.append(question.key())

    library.store_response('myid', quiz.key(), question_set[1], False, 3)

    # should we repeat to check for randomess?
    for i in range(0,10):
      picked_question = library.pick_next_question('myid', quiz.key(), False)
    
      possible_set = set([ str(question) for question in question_set])
      self.assertEquals(True, (str(picked_question.key()) in possible_set))

  def testValidWithNoAnsweredQuestionWithRepeat(self):
    question_set = []
    quiz_property = library.create_quiz_property()
    quiz = library.create_quiz(quiz_property=quiz_property, title='test')
    for i in range(0, 5):
      question = library.create_question(quiz)
      question_set.append(question.key())

    library.store_response('myid', quiz.key(), question_set[1], False, 3)

    # should we repeat to check for randomess?
    for i in range(0,10):
      picked_question = library.pick_next_question('myid', quiz.key(), True)
    
      possible_set = set([ str(question) for question in question_set])
      self.assertEquals(True, (str(picked_question.key()) in possible_set))

  def testValidSelectionWithRepeat(self):
    question_set = []
    quiz_property = library.create_quiz_property()
    quiz = library.create_quiz(quiz_property=quiz_property, title='test')
    for i in range(0, 5):
      question = library.create_question(quiz)
      question_set.append(question.key())

    # making entry for 3 questions
    for i in range(0,3):
      library.store_response('myid', quiz.key(), question_set[i], True, 3)

    # should we repeat to check for randomess?
    for index in range(0,10):
      picked_question = library.pick_next_question('myid', quiz.key(), True)
    
    # making set of 2 possible questions
      possible_set = set([ str(question_set[i]) for i in (3,4)])
      self.assertEquals(True, (str(picked_question.key()) in possible_set))

  def testValidSelectionWithRepeat(self):
    question_set = []
    quiz_property = library.create_quiz_property()
    quiz = library.create_quiz(quiz_property=quiz_property, title='test')
    for i in range(0, 5):
      question = library.create_question(quiz)
      question_set.append(question.key())

    # making entry for 3 questions
    for i in range(0,5):
      library.store_response('myid', quiz.key(), question_set[i], True, 3)

    # should we repeat to check for randomess?
    for index in range(0,5):
      picked_question = library.pick_next_question('myid', quiz.key(), True)
    
    # making set of 2 possible questions
      possible_set = set([ str(question_set[i]) for i in range(0,5)])
      self.assertEquals(True, (str(picked_question.key()) in possible_set))


class IncrementScoreTest(unittest.TestCase):
  """Tests question selection function. 
  TODO(mukundjha): Add some more relevant tests.
  """
  
  def testIncrementWithFirstAnswerFirstAttempt(self):
    question_set = []
    quiz_property = library.create_quiz_property()
    quiz = library.create_quiz(quiz_property=quiz_property, title='test')
    # Each question has 
    for i in range(0, 5):
      question = library.create_question(quiz)
      num_choices = 4
      for j in range(num_choices):
        choice = library.create_choice()
        question.choices.append(choice)

      question_set.append(question)
    score, status = library.increment_score('my_id',
                                             quiz,
                                             question_set[0],1)
    self.assertEquals(20 , score)
    self.assertEquals(round(status), round(100.0/5))
    query = models.QuizScoreModel.all().filter(
        'session_id =', 'my_id').filter('quiz =', quiz)
    self.assertEquals(1, query.count())
    self.assertEquals(score, query.get().score)
    self.assertEquals(round(query.get().progress), round(status))
 
   
  def testIncrementWithExistingScoreAndSecondAttempt(self):
    question_set = []
    quiz_property = library.create_quiz_property()
    quiz = library.create_quiz(quiz_property=quiz_property, title='test')
    # Each question has 
    for i in range(0, 5):
      question = library.create_question(quiz)
      num_choices = 4
      for j in range(num_choices):
        choice = library.create_choice()
        question.choices.append(choice)

      question_set.append(question)
    progress = 1.0/5.0
    library.insert_with_new_key(
        models.QuizScoreModel, session_id='my_id',quiz=quiz, score=5.0, 
        questions_attempted=1, quiz_trunk=quiz.trunk, progress=progress)
    
    score, status = library.increment_score('my_id',
                                             quiz,
                                             question_set[0],2)

    # score = 5 + (20 - (20/3)*(2-1))
    self.assertEquals(round(5.0+ (20.0 - (20.0/3.0))), round(score))
    self.assertEquals(round(200.0/5), round(status))
    query = models.QuizScoreModel.all().filter(
        'session_id =', 'my_id').filter('quiz =', quiz)
    self.assertEquals(1, query.count())
    self.assertEquals(query.get().score, score)
    self.assertEquals(round(query.get().progress), round(status))
    
    
if __name__ == "__main__":
  unittest.main()
