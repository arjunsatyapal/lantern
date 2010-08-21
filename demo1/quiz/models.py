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

"""App Engine data model (schema) definition for Quiz."""

# Python imports
import base64
import logging
import md5
import operator
import os
import re
import time

# AppEngine imports
from google.appengine.ext import db
from google.appengine.api import memcache


class QuizBaseModel(db.Model):
  """Base class for quiz models."""


class QuizTrunkModel(QuizBaseModel):
  """Maintains trunk for quiz model.

  Attributes:
    head: Maintians the head of a quiz.
  """
  head = db.StringProperty()


class QuizRevisionModel(QuizBaseModel):
  """Maintains list of revisions for a quiz.
  Quiz trunk associated with the revision is made parent of the model.
  
  Attributes:
    quiz_id: Id (key) for particular version of the quiz.
    time_stamp: Time_stamp for a new revision.
    commit_message: Commit message associated with new version.
  """
  quiz_id = db.StringProperty()
  time_stamp = db.DateTimeProperty(auto_now=True)
  commit_message = db.StringProperty(default='Commiting a new version')


class QuizPropertyModel(QuizBaseModel):
  """Defines various properties for a quiz.
 
  Attributes:
    shuffle_questions: If set questions are presented in random order.
    min_options: minimum number of options to be presented.
    max_options: maximum number of options to be presented.
    min_questions: minimum number of questions required to complete the quiz.
      Used to track the progress.
    repeat_questions: If set questions are repeated.
    repeat_wrongly_answered_questions: If set wrongly answered questions are
      repeated.
  """
  shuffle_questions = db.BooleanProperty(default=True)
  min_options = db.IntegerProperty(default=2) 
  max_options = db.IntegerProperty(default=10) # 0 implies all
  min_questions = db.IntegerProperty(default=0) # 0 implies all
  repeat_questions = db.BooleanProperty(default=False)
  repeat_wrongly_answered_questions = db.BooleanProperty(default=False)

    
class QuizModel(QuizBaseModel):
  """Represents a quiz.

  Attributes:
    difficulty_level: Difficulty level for the quiz (range 0-10).
    quiz_property: Reference to property asscociated with quiz.
    title: Title of the quiz.
    tags: Associated tags with quiz.
    trunk: Reference to asscociated trunk with the quiz.
    introduction: Introduction text to be shown on the start page for quiz.
  """
  # implicit id
  difficulty_level = db.RatingProperty(default=5)
  quiz_property = db.ReferenceProperty(QuizPropertyModel) 
  title = db.StringProperty()
  tags = db.ListProperty(db.Category)
  trunk = db.ReferenceProperty(QuizTrunkModel)
  introduction = db.StringProperty()
  

class ChoiceModel(QuizBaseModel):
  """Represents a choice/option provided to user for a question model.

  Attributes:
    body: Body of the choice.
    message: Message to be displayed when choice is selected.
      May act like a hint.
    is_correct: If the choice selected is correct.
  """
  # implicit id
  body = db.TextProperty()
  message = db.StringProperty()
  is_correct = db.BooleanProperty(default=False)

  def dump_to_dict(self):
    """Dumps choice to a dictionary for passing around as JSON object."""
    data_dict = {'body': self.body,
                'id': str(self.key())}
    return data_dict


class QuestionModel(QuizBaseModel):
  """Represents a question.
  
  Attributes:
    body: Text asscociated with quiz.
    choices: List of possible choices.
    shuffle_choices: If set choices are randomly shuffled.
    hints: Ordered list of progressive hints
  """
  # implicit id
  body = db.TextProperty()
  choices = db.ListProperty(db.Key)
  shuffle_choices = db.BooleanProperty(default=True)
  hints = db.StringListProperty()

  def dump_to_dict(self):
    """Dumps the question model to a dictionary for passing 
    around as JSON object."""
    data_dict = {'id': str(self.key()),
                 'body': self.body,
                 'hints': self.hints,
                 'choices': [db.get(el).dump_to_dict() for el in self.choices]
                }

    if self.shuffle_choices and data_dict['choices']:
      data_dict['choices'] = random.shuffle(data_dict['choices'])
    return  data_dict
   

class QuizQuestionListModel(QuizBaseModel):
  """Maintains a list of question with its quiz id.
  This is necessary because questions may be shared between different quizes.
  
  Attributes:
    quiz: Reference to quiz object.
    question: Reference to question object asscociated with quiz.
    time_stamp: Time stamp.
  """
  quiz = db.ReferenceProperty(QuizModel)  
  question = db.ReferenceProperty(QuestionModel)  
  time_stamp = db.DateTimeProperty(auto_now_add=True)


class ResponseModel(QuizBaseModel):
  """Stores response data required for producing next question.

  Attributes:
    session_id: Session Identifier.
    answered_correctly: Set if the response resulted in correct answer.
    question: Reference to question being answered.
    quiz: Reference to associated quiz.
    quiz_trunk: Reference to associated quiz trunk.
    time_stamp: Time stamp of the response
    attempts: Number of attempts so far, useful for scoring.
  """
  session_id = db.StringProperty(required=True)
  answered_correctly = db.BooleanProperty(db.Key)
  question = db.ReferenceProperty(QuestionModel)
  quiz = db.ReferenceProperty(QuizModel)
  quiz_trunk = db.ReferenceProperty(QuizTrunkModel)
  time_stamp = db.DateTimeProperty(auto_now=True)
  attempts = db.IntegerProperty(default=0)


class QuizScoreModel(QuizBaseModel):
  """Stores progress status associated with a quiz and session.
  
  Both score and progress are out of 100.
  Attributes:
    session_id: Session Identifier.
    quiz: Reference to associated quiz.
    quiz_trunk: Reference to associated quiz trunk.
    score: Current score.
    progress: Current progress status
    questions_attempted: Number of questions attempted so far.
  """
  quiz_trunk = db.ReferenceProperty(QuizTrunkModel)
  session_id = db.StringProperty(required=True)
  quiz = db.ReferenceProperty(QuizModel)
  score = db.FloatProperty(default=0.0)
  progress = db.FloatProperty(default=0.0)
  questions_attempted = db.IntegerProperty(default=0)
