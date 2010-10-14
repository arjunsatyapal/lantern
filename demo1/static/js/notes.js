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
 * @fileoverview This module contains code for managing the display and
 *     recording of user notes. It contains:
 * <ul>
 *  <li>NoteButton that binds to the BUTTON element to manage the interaction
 *    between UI events and the loading and updating of a note. One of these
 *    is bound to each note button.
 *  <li>NoteEditor is the popup editor that allows the user to enter/modify
 *    the note.
 *  <li>NoteManager manages all notes within a page. It is used to decorate all
 *    note buttons on the page. Its dispose() method should be called when
 *    the page unloads to release resources.
 *  <li>NoteProvider manages the XHR communications, exposing getNote()
 *    and updateNote() methods.
 * </ul>
 *
 * Expectation:
 *
 * For each note on a page, there is:
 * <ul>
 *  <li>A (hidden) textarea element that shows the annotation
 *   (annotation id) and is given ("note-" + id) as its id attribute.
 *  <li>A BUTTON element with id ("note-" + id + "-button") that wraps a
 *   ball icon. Its on-click event is used to pop up an editor.
 *  <li>A colored ball icon with id ("note-" + id + "-ball") that reflects
 *   whether there is a note.
 * </ul>
 * The string used in the elementIds is the ID of the doc-content object to
 * be associated with the note. (Formerly, it was the ID of the annotation
 * object).
 *
 * This note-handling functionality is triggered upon clicking the ball to
 * unhide the annotation, and then arrange for the updated annotation to be
 * sent back when the textarea is hidden again via onHide_ callback.
 */

goog.provide('lantern.notes.NoteButton');
goog.provide('lantern.notes.NoteEditor');
goog.provide('lantern.notes.NoteManager');
goog.provide('lantern.notes.NoteProviderXhr');

goog.require('goog.array');
goog.require('goog.Disposable');
goog.require('goog.dom');
goog.require('goog.events.EventHandler');
goog.require('goog.json');
goog.require('goog.net.XhrIo');
goog.require('goog.string');
goog.require('goog.ui.Popup');
goog.require('goog.Uri');

goog.require('lantern.DataProviderXhr');


/**
 * ID suffix for the associated button element.
 * @type {string}
 * @private
 */
lantern.notes.SUFFIX_BUTTON_ = "-button";


/**
 * ID suffix for the associated button image
 * @type {string}
 * @private
 */
lantern.notes.SUFFIX_IMAGE_ = "-ball";


/**
 * A class for handling the display and editing of a note.  It uses the supplied
 * XHR helper to get and save notes from the server.
 *
 * One instance should be created for each note. The constructor also binds
 * this instance to handle click events on the underlying button.
 *
 * @param {string} trunk_id ID of the doc trunk.
 * @param {string} doc_id ID of the doc that instantiated this manager.
 * @param {string} name The key of the content object to which the
 *     annotation is attached. It is expected to have a prefix of "note-".
 * @param {element} buttonElt The button Element on which to tie a click event.
 * @param {lantern.notes.NoteProvider} xhrHelper The helper to use to get
 *     and update notes. This is a shared reference.
 * @constructor
 * @extends {goog.Disposable}
 */
lantern.notes.NoteButton = function(
    trunk_id, doc_id, name, buttonElt, xhrHelper) {
  goog.Disposable.call(this);

  /**
   * Trunk Id of the doc to which this note is attached.
   * @type {string}
   * @private
   */
  this.trunk_id_ = trunk_id;

  /**
   * Doc Id of the doc to which this note is attached.
   * @type {string}
   * @private
   */
  this.doc_id_ = doc_id;

  /**
   * Name of the button element that contains the key of the content to
   * which the annotation is attached.
   * @type {string}
   * @private
   */
  this.name_ = name;

  /**
   * Button element to which to bind.
   * @type {element}
   * @private
   */
  this.buttonElt_ = buttonElt;


  /**
   * Helper to get/update notes via XHR.
   * @type {lantern.notes.NoteProvider}
   * @private
   */
  this.xhrHelper_ = xhrHelper;

  /**
   * Event handler helper.
   * @type {goog.events.EventHandler}
   * @private
   */
  this.eh_ = new goog.events.EventHandler(this);

  this.bind_();
};
goog.inherits(lantern.notes.NoteButton, goog.Disposable);


/**
 * Default message to display in a new Note.
 * @type {string}
 * @private
 */
lantern.notes.NoteButton.DEFAULT_PROMPT_ = "Type your notes here...";


/**
 * @override
 */
lantern.notes.NoteButton.prototype.disposeInternal = function() {
  lantern.notes.NoteButton.superClass_.disposeInternal.call(this);

  this.eh_.dispose();
  this.eh_ = null;
  this.buttonElt_ = null;
  this.name_ = null;
  this.xhrHelper_ = null;  // Do not call dispose(), since it is shared.
};


/**
 * Binds the instance to the underlying event and trigger a load of the note
 * in order to set the button image.
 * @private
 */
lantern.notes.NoteButton.prototype.bind_ = function() {
  if (this.buttonElt_) {
    this.eh_.listen(this.buttonElt_, goog.events.EventType.CLICK,
                    this.showNote_);
  }
  this.getNote_(null);  // Get the note, but no popups.
};


/**
 * Shows the note. This is installed as the click handler.
 * @private
 */
lantern.notes.NoteButton.prototype.showNote_ = function(e) {
  var noteElt = document.getElementById(this.name_);

  // Constructs the popup editor and install a handler for recording updates.
  var popup = new lantern.notes.NoteEditor(
      noteElt, goog.bind(this.handleEditorUpdate_, this));

  // The user clicked the ball; we grab the current annotation
  // from the server and when the response comes back stuff it
  // in the textarea and pop it up.
  this.getNote_(popup);
};


/**
 * Handles update from editor. Grabs the updated annotation from the textarea
 * and sends it to the server.
 * @private
 */
lantern.notes.NoteButton.prototype.handleEditorUpdate_ = function(noteElt) {
  var contents = noteElt.value;
  var ball = '';

  // NEEDSWORK: while popping down if the text matches the prompt
  // *AND* if the whole text is still selected, the user opened and
  // then dismissed the popup without doing anything.  In that case
  // (and only in that case), we probably should avoid updating the
  // annotation with this text.  I do not know how we can check the
  // latter condition, though...
  if (contents == lantern.notes.NoteButton.DEFAULT_PROMPT_) {
    contents = '';
  }

  // Paint a non-empty annotation in 'positive' color.
  // NEEDSWORK: add a control to the "notes" widget for the user to
  // say "Like", "Dislike", etc.
  if (contents != '') {
    ball = 'pos';
  } else {
    ball = 'plain';
  }
  // Sends the data to the server, installing a callback to get the note again
  // in order to set the image appropriately.
  // TODO(vchen): Is that too expensive? Should we set the image directly?
  this.xhrHelper_.updateNote(
      this.trunk_id_, this.doc_id_, this.name_, contents, ball, xsrfToken,
      goog.bind(this.getNote_, this, null));
};


/**
 * Convenience routine to issue the async call to get the note.
 *
 * @param {goog.ui.Popup} opt_popup If specified, the popup will be shown then
 *     the note is received from the server.
 */
lantern.notes.NoteButton.prototype.getNote_ = function(opt_popup) {
  this.xhrHelper_.getNote(
      this.trunk_id_, this.doc_id_, this.name_, xsrfToken,
      goog.bind(this.processNote_, this, opt_popup));
};


/**
 * Processes a note returned from the XHR getNote() call.
 *
 * @param {goog.ui.Popup?} popup If specified, set the contents of the associated
 *    textarea and show the note in a popup. Otherwise, just set the ball image.
 * @param {string} id Request ID of the underlying XHR call. Ignored.
 * @param {Object} result Data returned by XHR for the note. It contains
 *    'text' and 'ball'.
 * @param {string?} opt_errMsg Optional error message return from the XHR call.
 */
lantern.notes.NoteButton.prototype.processNote_ = function(
    popup, id, result, opt_errMsg) {

  var ball = this.sanitizeBallColor_(result['ball']);

  var ballElt = document.getElementById(
      this.name_ + lantern.notes.SUFFIX_IMAGE_);
  ballElt.src = '/static/images/note-' + ball + '.png';
  if (popup) {
    var noteElt = document.getElementById(this.name_);
    if (noteElt) {
      if (noteElt.value != result['text']) {
        noteElt.value = result['text'];
      }
      popup.setVisible(true);

      if (result['text'] == '') {
        // When empty (i.e. no annotation), urge the user to type
        // something, but select all so that the first keystroke
        // would dismiss the prompt.
        noteElt.value = lantern.notes.NoteButton.DEFAULT_PROMPT_;
        noteElt.select();
      }
      // Get the focus to allow the user to immediately start typing
      noteElt.focus();
    }
  }
};


/**
 * Ensures the ball name is one of the valid "enum" values.
 * @param {string} ball The "type" of ball to display as the image. Acceptable
 *     values are 'plain', 'pos', 'neg'. If it is not one of those, returns
 *     'plain'.
 * @private
 */
lantern.notes.NoteButton.prototype.sanitizeBallColor_ = function(ball) {
  switch (ball) {
    case 'plain':
    case 'pos':
    case 'neg':
      break;
    default:
      ball = 'plain';
     break;
  }
  return ball;
};


// ------------------------------------------


/**
 * Popup editor for user notes.
 * @param {element} contentEl Element to display within the Popup as its
 *     contents.
 * @param {Function} onUpdateCallback Callbak to be called with the
 *     contentEl element.
 *
 * @constructor
 * @extends {goog.ui.Popup}
 */
lantern.notes.NoteEditor = function(contentEl, onUpdateCallback) {
  goog.ui.Popup.call(this, contentEl);

  /**
   * Callback function when the note should be updated.
   * @type {Function}
   * @private
   */
  this.callback_ = onUpdateCallback;

};
goog.inherits(lantern.notes.NoteEditor, goog.ui.Popup);


/**
 * @override
 */
lantern.notes.NoteEditor.prototype.disposeInternal = function() {
  this.callback_ = null;
};


/**
 * @override
 */
lantern.notes.NoteEditor.prototype.onHide_ = function() {
  goog.ui.PopupBase.prototype.onHide_.call(this);

  if (this.callback_) {
    this.callback_(this.getElement());
  }
};


// ------------------------------


/**
 * Manager for instrumenting all the notes on a page.
 *
 * @param {string} className Name of the class used to mark BUTTON elements
 *     that should be bound to NoteButtons.
 * @param {string} trunk_id ID of the doc trunk.
 * @param {string} doc_id ID of the doc that instantiated this manager.
 * @constructor
 * @extends {goog.Disposable}
 */
lantern.notes.NoteManager = function(className, trunk_id, doc_id) {
  goog.Disposable.call(this);

  this.xhrHelper_ = new lantern.notes.NoteProvider();

  this.noteButtons_ = [];

  var notes = goog.dom.getElementsByTagNameAndClass('button', className);
  var num = notes.length;
  for (var i = 0; i < num; i++) {
    var button = notes[i];
    var id = button.id;
    if (goog.string.endsWith(id, lantern.notes.SUFFIX_BUTTON_)) {
      // Strip suffix to determine the name of the textarea.
      id = id.replace(lantern.notes.SUFFIX_BUTTON_, '');
    }
    var noteButton = new lantern.notes.NoteButton(
        trunk_id, doc_id, id, button, this.xhrHelper_);
    this.noteButtons_.push(noteButton);
  }
};
goog.inherits(lantern.notes.NoteManager, goog.Disposable);


lantern.notes.NoteManager.prototype.disposeInternal = function() {
  lantern.notes.NoteManager.superClass_.disposeInternal.call(this);

  var num = this.noteButtons_.length;
  for (var i = 0; i < num; i++) {
    this.noteButtons_[i].dispose();
    this.noteButtons_[i] = null;
  }
  this.xhrHelper_.dispose();

  this.noteButtons_ = null;
  this.xhrHelper_ = null;
}


// ------------------------------


/**
 * The NoteProvider has methods for retrieving and saving notes via XHR:
 *
 * - getNote()
 * - updateNote()
 *
 * It uses the following URI for XHR via POST:
 *  /notes/get  Gets the specified note.
 *    input: data=dataDict&amp;xsrf_token=xsrfToken
 *      where dataDict is a JSON-encoded dict of the form:
 *       {'name': key}
 *      and key is the ID of the content to which the annotation is attached.
 *    output: JSON-encoded dictionary of the form:
 *       {
 *        'text': contents,
 *        'ball': marker
 *       }
 *      where the marker specifies the type of the marker, 'plain', 'pos'.
 *
 *  /notes/update Updates the specified note.
 *     input: data=dataDict&amp;xsrf_token=xsrfToken
 *       where dataDict is a JSON-encoded dict of the form:
 *        {
 *         'name': key,
 *         'text': contents,
 *         'ball': marker
 *        }
 *      and key is the ID of the content to which the annotation is attached.
 *     output: HTML-formmated debug info.
 *
 * @constructor
 * @extends {goog.Disposable}
 */
lantern.notes.NoteProvider = function() {
  goog.Disposable.call(this);

  /**
   * Manager for XHR requests.
   * @type {lantern.DataProviderXhr}
   * @private
   */
  this.xhr_ = new lantern.DataProviderXhr();
};
goog.inherits(lantern.notes.NoteProvider, goog.Disposable);


/**
 * Monotonically increasing counter for the request ID.
 * @type {number}
 * @private
 */
lantern.notes.NoteProvider.currentRequestId_ = 0;


/**
 * Default base URL for XHR requests.
 * @type {string}
 * @private
 */
lantern.notes.NoteProvider.DEFAULT_XHR_URI_ = '/notes/';


/**
 * Gets the specified note asynchronously, invoking the callback when the
 * response is received.
 *
 * @param {string} trunk_id The Trunk Id of the document.
 * @param {string} doc_id The ID of the document.
 * @param {string} content_id The ID of the doc content to which the note
 *     is attached.
 * @param {string} xsrfToken The XSRF token to use to post the request.
 * @param {Function} callback The callback function. It has the signature:
 *    callback(request_id, result, opt_errMsg)
 */
lantern.notes.NoteProvider.prototype.getNote = function(
    trunk_id, doc_id, content_id, xsrfToken, callback) {
  var uri = this.getXhrUri_('get');
  var data = {
    'trunk_id': trunk_id,
    'doc_id': doc_id,
    'name': content_id
  };
  var contents = ["data=",
                  goog.json.serialize(data),
                  '&amp;xsrf_token=',
                  xsrfToken].join('');
  var id = lantern.notes.NoteProvider.currentRequestId_++;
  this.xhr_.sendRequest(id, uri, callback, 'POST', contents);
};


/**
 * Updates the specified note asynchronously, invoking the callback when the
 * response is received.
 *
 * @param {string} trunk_id The Trunk Id of the document.
 * @param {string} doc_id The ID of the document.
 * @param {string} content_id The ID of the doc content to which the note
 *     is attached.
 * @param {string} contents The contents of the note.
 * @param {string} ball The marker type, e.g., 'plain', 'pos', 'neg'.
 * @param {string} xsrfToken The XSRF token to use to post the request.
 * @param {Function} callback The callback function. It has the signature:
 *    callback(request_id, result, opt_errMsg)
 */
lantern.notes.NoteProvider.prototype.updateNote = function(
    trunk_id, doc_id, content_id, contents, ball, xsrfToken, callback) {
  var uri = this.getXhrUri_('update');
  var data = {
    'trunk_id': trunk_id,
    'doc_id': doc_id,
    'name': content_id,
    'text': contents,
    'ball': ball
  };
  var contents = ["data=",
                  goog.json.serialize(data),
                  '&amp;xsrf_token=',
                  xsrfToken].join('');
  var id = lantern.notes.NoteProvider.currentRequestId_++;
  this.xhr_.sendRequest(id, uri, callback, 'POST', contents);
};
/**
 * Returns the URI to use for XHR.
 * @param {string?} action The action, 'get' or 'update'.
 * @return {goog.Uri}
 */
lantern.notes.NoteProvider.prototype.getXhrUri_ = function(action) {
  var uri = new goog.Uri(lantern.notes.NoteProvider.DEFAULT_XHR_URI_
                         + (action ? action : ''));
  return uri;
};


/**
 * @override
 */
lantern.notes.NoteProvider.prototype.disposeInternal = function() {
  lantern.notes.NoteProvider.superClass_.disposeInternal.call(this);
  this.xhr_.dispose();
  this.xhr_ = null;
};
