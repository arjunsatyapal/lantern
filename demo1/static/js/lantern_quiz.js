// Copyright 2010 Google Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
// 
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.


/**
 * @fileoverview Script for presenting quiz and collecting response.
 * To be included in main quiz page.
 */

goog.provide('lantern.quiz.QuizSession');

goog.require('goog.dom')
goog.require('goog.net.XhrIo');
goog.require('goog.ui.Button');
goog.require('goog.ui.ButtonRenderer');
goog.require('goog.Uri');


/**
 * Constructor for Lantern Quiz Session.
 * @param {string} quizTrunkId Quiz's trunk id.
 * @param {string} quizId Id of the quiz being presented.
 * @constructor
 */
lantern.quiz.QuizSession = function(quizTrunkId, quizId) {
  this.quizId_ = quizId;
  this.quizTrunkId_ = quizTrunkId;
  this.widgetChannel_  = new lantern.widget.LanternWidgetChannel();
  this.widgetChannel_.initializeChannel(goog.bind(this.getSessionId, this));
  this.sessionId_ = '';
  this.question_ = {};
  this.attempts_ = 0;
  this.xhr_ = new goog.net.XhrIo();
};


/**
 * Callback to initiate quiz immediately after loading.
 * NOTE(mukundjha): This sometimes work properly on firefox, but
 * almost never on Chrome. This is due to delay in setting up the
 * channel.
 */
lantern.quiz.QuizSession.prototype.getSessionId = function(){
  this.widgetChannel_.getDataAsync(goog.bind(this.initQuiz, this));
};


/**
 * Initiates the quiz by making AJAX call to load new question.
 * @param {string} session_id Unique session identifier.
 */
lantern.quiz.QuizSession.prototype.initQuiz = function(session_id) {
  this.sessionId_ = session_id;
  this.getNextQuestion();
};


/**
 * Sends an AJAX call to fetch new question.
 */
lantern.quiz.QuizSession.prototype.getNextQuestion = function() {
  goog.events.removeAll(this.xhr_);
  goog.events.listen(
      this.xhr_, goog.net.EventType.COMPLETE,
      goog.bind(this.presentQuiz, this));

  var uri = new goog.Uri('/quiz/getQuestion');
  uri.setParameterValue('quiz_id', this.quizId_);
  uri.setParameterValue('quiz_trunk_id', this.quizTrunkId_);
  uri.setParameterValue('session_id', this.sessionId_);

  this.xhr_.send(uri);
};


/**
 * Method to create DOM to present quiz.
 * Also binds response function (defined in quiz.html) to choice click event.
 * @param {Object} obj Data object sent by quiz server required for rendring
 *   new question.
 * TODO(mukundjha): Remove dependency on quiz.html by using event handler.
 */
lantern.quiz.QuizSession.prototype.makeQuizDOM = function(obj) {
  if (obj.error_msg) {
     var questionContainer = goog.dom.getElement('questionContainer');
      goog.dom.removeChildren(questionContainer);
     var displayMessage = 'Sorry, unable to show the quiz!!' + obj.error_msg;
     questionContainer.appendChild(goog.dom.createTextNode(displayMessage));
     return;
  }
  if (obj.current_status) {
    this.updateStatus(obj.current_status)
  }
  
  goog.dom.removeChildren(goog.dom.getElement('quizButtonContainer'));
  goog.dom.removeChildren(goog.dom.getElement('quizMessage'));
  goog.dom.removeChildren(goog.dom.getElement('nextQuestionBox'));
  goog.dom.removeChildren(goog.dom.getElement('questionBody'));
  goog.dom.removeChildren(goog.dom.getElement('choices'));
  
  this.attempts_ = obj.attempts;
  var questionBodyContainer = goog.dom.getElement('questionBody');
  questionBodyContainer.appendChild(
      goog.dom.createDom('div', {'class': 'lanternQuizLabel'}, 'Question:'));
  questionBodyContainer.appendChild(
      goog.dom.createDom('div', {'class': 'lanternQuizQuestion'},
                         obj.question.body));
  
  var choiceContainer = goog.dom.getElement('choices');
  choiceContainer.appendChild(goog.dom.createDom('br'));
  choiceContainer.appendChild(
      goog.dom.createDom('div', {'class': 'lanternQuizLabel'},
                         'Please select among the following choices:'));

  choiceContainer.appendChild(goog.dom.createDom('br'));
  alert(obj.question.choices.length)
  for (var i=0; i< obj.question.choices.length; i++) {
    var choice = goog.dom.createDom('input', {
       'type': 'radio',
       'id': 'answer' + i,
       'name': 'answer', 
       'value': obj.question.choices[i].id});

    choiceContainer.appendChild(choice);
    var choiceLabel = goog.dom.createDom('label', { 'for': 'answer' + i},
                                         obj.question.choices[i].body);
   
    choiceContainer.appendChild(choiceLabel);
    choiceContainer.appendChild(goog.dom.createDom('br'));
    goog.events.listen(choice, goog.events.EventType.CLICK,
                       goog.bind(this.collectResponse, this,
                                  obj.question.choices[i].id));
  }

};


/**
 * Callback to present new question once its fetched.
 */
lantern.quiz.QuizSession.prototype.presentQuiz = function(e) {
  
  var obj = this.xhr_.getResponseJson();
  this.question_ = obj.question;
  this.makeQuizDOM(obj);
};


/**
 * Function to send request to reset the quiz scores.
 * Upon resetting a new question is fetched and is passed 
 * to presentQuiz.
 */
lantern.quiz.QuizSession.prototype.resetQuiz = function() {
  goog.events.removeAll(this.xhr_);
  goog.events.listen(
      this.xhr_, goog.net.EventType.COMPLETE,
      goog.bind(this.presentQuiz, this));

  var uri = new goog.Uri('/quiz/resetQuiz');
  uri.setParameterValue('quiz_id', this.quizId_);
  uri.setParameterValue('quiz_trunk_id', this.quizTrunkId_);
  uri.setParameterValue('session_id', this.sessionId_);
  this.xhr_.send(uri);
};


/**
 * Helper function to update DOM associated with updating score.
 * @param {object} current_status Current progress status.
 */
lantern.quiz.QuizSession.prototype.updateStatus = function(current_status){

  this.widgetChannel_.updateScore(current_status);
      
  progressHtmlArray = [
      '<table border="0"><tr><td><b>Score: </b></td><td><b>',
      current_status.score, '</b></td></tr><tr><td><b>Progress:</b></td><td>',
      '<img src="http://chart.apis.google.com/chart?chs=150x25&chd=t:',
      current_status.progress,
      '|100&cht=bhs&chds=0,100&chco=4D89F9,C6D9FD&chxt=y,r&chxl=0:||1:||',
      '&chm=N,000000,0,-1,11"', '</td></tr></table>'];

  var progressBox = goog.dom.getElement('progressBox');
  progressBox.innerHTML = progressHtmlArray.join('');

  var resetMessage = goog.dom.getElement('resetMessage');
  if (resetMessage) {
    goog.dom.removeChildren(resetMessage);
  }
  var resetButtonContainer = goog.dom.getElement('resetButton');
  if (resetMessage) {
    goog.dom.removeChildren(resetButtonContainer);
  }

  if (current_status.progress == 100) {
    var resetButton = new goog.ui.Button('Reset Scores');
    resetButton.render(resetButtonContainer);
    
    var message = 'You have completed the required questions.' + 
                  'Click reset if you wish to reset the scores';

    goog.events.listen(resetButton, goog.ui.Component.EventType.ACTION,
			goog.bind(this.resetQuiz, this));

    resetMessage.innerHTML = message;
  }
};


/**
 * Updates quiz DOM after user selects a choice based on
 * response from the server.
 * @param {object} obj Data passed by the server for updating the DOM.
 */
lantern.quiz.QuizSession.prototype.updateQuizDOM = function(obj) {

  if (obj.error_msg) {
     var questionContainer = goog.dom.getElement('questionContainer');
      goog.dom.removeChildren(questionContainer);
     var displayMessage = 'Sorry, unable to show the quiz!!' + obj.error_msg;
     questionContainer.appendChild(goog.dom.createTextNode(displayMessage));
     return;
  }
  if (obj.current_status) {
    this.updateStatus(obj.current_status);      
  }

  var messageContainer = goog.dom.getElement('quizMessage');
  goog.dom.removeChildren(messageContainer);
  var nextQuestionBox = goog.dom.getElement('nextQuestionBox');
  goog.dom.removeChildren(nextQuestionBox);

  if (obj.accepted) {
    messageContainer.appendChild(
        goog.dom.createDom('div', {'class': 'lanterQuizSuccessMessage' },
                            obj.message));
    var nextButton = new goog.ui.Button('Next Question');
    nextButton.render(nextQuestionBox);
    goog.events.listen(nextButton, goog.ui.Component.EventType.ACTION,
                       goog.bind(this.getNextQuestion, this));
  }
  else{
    messageContainer.appendChild(
        goog.dom.createDom('div', {'class': 'lanterQuizFailureMessage' },
                            obj.message));
  }
};


/**
 * Function to process server's response to user's selection.
 */
lantern.quiz.QuizSession.prototype.processResponse = function(e) {
  
 // alert('presenting quiz');
  var obj = this.xhr_.getResponseJson();
  if (obj.progress){
    this.widgetChannel_.updateScore(obj.progress);
  }
  this.updateQuizDOM(obj);
};


/**
 * Collects user's response/selection and passes to server to check
 * validity.
 *
 * @param {string} choice Key of the selected choice.
 */
lantern.quiz.QuizSession.prototype.collectResponse = function(choice) {
  this.attempts_ += 1
  goog.events.removeAll(this.xhr_);

  goog.events.listen(
      this.xhr_, goog.net.EventType.COMPLETE,
      goog.bind(this.processResponse, this));

  var uri = new goog.Uri('/quiz/collectResponse');
  uri.setParameterValue('quiz_id', this.quizId_);
  uri.setParameterValue('question_id', this.question_.id);
  uri.setParameterValue('quiz_trunk_id', this.quizTrunkId_);
  uri.setParameterValue('session_id', this.sessionId_);
  uri.setParameterValue('attempts', this.attempts_);
  uri.setParameterValue('answer', choice);
  this.xhr_.send(uri)
};

/**
 * Initializes quiz by asking for session_id from parent doc.
 */
lantern.quiz.QuizSession.prototype.init = function() {
  this.widgetChannel_.getDataAsync(
      goog.bind(this.initQuiz, this));
}
