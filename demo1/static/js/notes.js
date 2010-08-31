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

goog.require('goog.ui.Popup');
goog.require('goog.net.XhrIo');
goog.require('goog.Uri');
goog.require('goog.json');
goog.provide('lantern.Notes');
goog.provide('lantern.Notes.showNote');
goog.provide('lantern.Notes.paintBall');

lantern.Notes.StartTypingPrompt = "Type your notes here...";

lantern.Notes.SanitizeBallColor = function(ball) {
  switch (ball) {
    default:
      ball = 'plain';
    case 'plain': case 'pos': case 'neg':
      break;
  }
  return ball;
};

lantern.Notes.showNote = function(name) {
  // A hidden textarea element to show the annotation (annotation id)
  // is given ("note-" + id) as its id attribute, and a colored
  // ball icon that pops up the annotation is named ("note-" + id + "-ball").
  // This function is triggered upon clicking the ball to unhide the
  // annotation, and then arrange the updated annotation to be sent back
  // when the textarea is hidden again via onHide_ callback implemented
  // in goog.ui.PopupBase class.
  var noteElt = document.getElementById(name);
  var ballElt = document.getElementById(name + '-ball');
  var note = new goog.ui.Popup(noteElt);

  note.onHide_ = function(opt_target) {
    // When goog.ui.Popup() is dismissed, this gets called; we grab
    // the updated annotation out of the textarea and send it back
    // to the server here.
    var contents = noteElt.value;
    var ball = '';
    var uri = new goog.Uri('/notes/update');

    // NEEDSWORK: while popping down if the text matches the prompt
    // *AND* if the whole text is still selected, the user opened and
    // then dismissed the popup without doing anything.  In that case
    // (and only in that case), we probably should avoid updating the
    // annotation with this text.  I do not know how we can check the
    // latter condition, though...
    if (contents == lantern.Notes.StartTypingPrompt)
      contents = '';

    // Paint a non-empty annotation in 'positive' color.
    // NEEDSWORK: add a control to the "notes" widget for the user to
    // say "Like", "Dislike", etc.
    if (contents != '')
      ball = 'pos';
    else
      ball = 'plain';

    var data = goog.json.serialize({
      'name': name,
      'text': contents,
      'ball': ball
    });
    // alert("Sending " + data);

    goog.net.XhrIo.send(uri, function(e) {
      var xhr = e.target;
      var obj = xhr.getResponseText();
      lantern.Notes.paintBall(name);
    }, "POST", "data=" + data + "&amp;xsrf_token=" + xsrfToken);

    goog.ui.PopupBase.prototype.onHide_.call(note);
  };

  var uri = new goog.Uri('/notes/get');
  var data = goog.json.serialize({ 'name': name });

  // The user clicked the ball; we grab the current annotation
  // from the server and when the response comes back stuff it
  // in the textarea and pop it up.
  goog.net.XhrIo.send(uri, function(e) {
    var xhr = e.target;
    var obj = xhr.getResponseJson();
    var ball = lantern.Notes.SanitizeBallColor(obj['ball'])

    ballElt.src = '/static/images/note-' + ball + '.png';

    if (noteElt.value != obj['text'])
      noteElt.value = obj['text'];
    note.setVisible(true);

    if (obj['text'] == "") {
      // When empty (i.e. no annotation), urge the user to type
      // something, but select all so that the first keystroke
      // would dismiss the prompt.
      noteElt.value = lantern.Notes.StartTypingPrompt;
      noteElt.select();
    }

    // Get the focus to allow the user to immediately start typing
    noteElt.focus();
  }, "POST", "data=" + data + "&amp;xsrf_token=" + xsrfToken);
};

lantern.Notes.paintBall = function(name) {
  // After a page is loaded, update the color of balls on the page
  // to match what is stored on the server end.
  var ballElt = document.getElementById(name + '-ball');
  var uri = new goog.Uri('/notes/get');
  var data = goog.json.serialize({ 'name': name });

  goog.net.XhrIo.send(uri, function(e) {
      var xhr = e.target;
      var obj = xhr.getResponseJson();
      var ball = lantern.Notes.SanitizeBallColor(obj['ball'])

      ballElt.src = '/static/images/note-' + ball + '.png';
    }, "POST", "data=" + data);

}
