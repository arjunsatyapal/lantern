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
 * @fileoverview This module contains code for ww HTML editor
 */

goog.provide('lantern.wwedit.NotepadManager');

goog.require('goog.dom');
goog.require('goog.editor.Command');
goog.require('goog.editor.SeamlessField');
goog.require('goog.editor.ClickToEditWrapper');
goog.require('goog.editor.plugins.BasicTextFormatter');
goog.require('goog.editor.plugins.EnterHandler');
goog.require('goog.editor.plugins.HeaderFormatter');
goog.require('goog.editor.plugins.LinkBubble');
goog.require('goog.editor.plugins.LinkDialogPlugin');
goog.require('goog.editor.plugins.ListTabHandler');
goog.require('goog.editor.plugins.LoremIpsum');
goog.require('goog.editor.plugins.RemoveFormatting');
goog.require('goog.editor.plugins.SpacesTabHandler');
goog.require('goog.editor.plugins.UndoRedo');
goog.require('goog.ui.editor.DefaultToolbar');
goog.require('goog.ui.editor.ToolbarController');
goog.require('goog.events.EventHandler');
goog.require('goog.style');

goog.require('lantern.DataProviderXhr');

/**
 * Keep track of all the NotePad on a page, so that
 * we can get rid of them at once at the end
 */
lantern.wwedit.NotepadManager = function () {
  goog.Disposable.call(this);
  var notepads = goog.dom.getElementsByTagNameAndClass('div', 'notepad');
  this.notepads_ = []
  for (var i = 0; i < notepads.length; i++) {
    this.notepads_.push(new lantern.wwedit.NotePad(notepads[i]));
  }
};
goog.inherits(lantern.wwedit.NotepadManager, goog.Disposable);


/**
 * @override
 */
lantern.wwedit.NotepadManager.prototype.disposeInternal = function() {
  for (var i = 0; i < this.notepads_.length; i++) {
    var notepad = this.notepads_[i];
    notepad.dispose();
  }
  this.notepads_ = null;
};

lantern.wwedit.isNotePadKey_ = function (node) {
  return (node.tagName == 'INPUT') && (node.name == 'key');
};

lantern.wwedit.isNotePadEdit_ = function (node) {
  return (node.tagName == 'DIV') && (node.className == 'googedit');
};

lantern.wwedit.isNotePadEditToolbar_ = function (node) {
  return (node.tagName == 'DIV') && (node.className == 'edittb');
};

lantern.wwedit.NotePad = function (node) {
  goog.Disposable.call(this);
  var notepadKey = goog.dom.findNode(node, lantern.wwedit.isNotePadKey_);
  this.notepadId_ = notepadKey.value;
  this.notepadEdit_ = goog.dom.findNode(node, lantern.wwedit.isNotePadEdit_);
  this.notepadEditToolbar_ = goog.dom.findNode(node, lantern.wwedit.isNotePadEditToolbar_);
  if (!this.notepadEdit_.id) {
    this.notepadEdit_.id = 'wwedit' + lantern.wwedit.NotePad.IdSequence_++;
  }
  this.notepadField_ = new goog.editor.SeamlessField(this.notepadEdit_.id);
  this.notepadCTEW_ = new goog.editor.ClickToEditWrapper(this.notepadField_);

  this.xhr_ = new lantern.DataProviderXhr();
  this.currentRequestId_ = 0;
  this.eh_ = new goog.events.EventHandler(this);

  var key = this.notepadId_;
  this.sendRequest('/notepad/get',
                   goog.bind(this.receiveNotePadValue_, this, null),
                   'POST',
                   'key=' + encodeURIComponent(key) + '&amp;' +
                   'xsrf_token=' + xsrfToken);
};
goog.inherits(lantern.wwedit.NotePad, goog.Disposable);

/**
 * @private
 */
lantern.wwedit.NotePad.IdSequence_ = 0;

lantern.wwedit.NotePad.prototype.receiveNotePadValue_ = function(
    callback, requestId, result, opt_errMsg) {
  var myField = this.notepadField_;

  text = (result ? result.text : "");
  if (text == "") {
    text = "<br />";
  }
  myField.setHtml(false, text);

  // Create and register all of the editing plugins you want to use.
  myField.registerPlugin(new goog.editor.plugins.BasicTextFormatter());
  myField.registerPlugin(new goog.editor.plugins.RemoveFormatting());
  myField.registerPlugin(new goog.editor.plugins.UndoRedo());
  myField.registerPlugin(new goog.editor.plugins.ListTabHandler());
  myField.registerPlugin(new goog.editor.plugins.SpacesTabHandler());
  myField.registerPlugin(new goog.editor.plugins.EnterHandler());
  myField.registerPlugin(new goog.editor.plugins.HeaderFormatter());
  myField.registerPlugin(
      new goog.editor.plugins.LoremIpsum('Click here to edit'));
  myField.registerPlugin(
      new goog.editor.plugins.LinkDialogPlugin());
  myField.registerPlugin(new goog.editor.plugins.LinkBubble());

  // Specify the buttons to add to the toolbar, using built in default buttons.
  var buttons = [
      goog.editor.Command.BOLD,
      goog.editor.Command.ITALIC,
      goog.editor.Command.UNDERLINE,
      goog.editor.Command.FONT_COLOR,
      goog.editor.Command.BACKGROUND_COLOR,
      goog.editor.Command.FONT_FACE,
      goog.editor.Command.FONT_SIZE,
      goog.editor.Command.LINK,
      goog.editor.Command.UNDO,
      goog.editor.Command.REDO,
      goog.editor.Command.UNORDERED_LIST,
      goog.editor.Command.ORDERED_LIST,
      goog.editor.Command.INDENT,
      goog.editor.Command.OUTDENT,
      goog.editor.Command.JUSTIFY_LEFT,
      goog.editor.Command.JUSTIFY_CENTER,
      goog.editor.Command.JUSTIFY_RIGHT,
      goog.editor.Command.SUBSCRIPT,
      goog.editor.Command.SUPERSCRIPT,
      goog.editor.Command.STRIKE_THROUGH,
      goog.editor.Command.REMOVE_FORMAT
                 ];
  var myToolbar = goog.ui.editor.DefaultToolbar.makeToolbar(
      buttons,
      this.notepadEditToolbar_);

  // Hook the toolbar into the field.
  var myToolbarController =
      new goog.ui.editor.ToolbarController(myField, myToolbar);

  goog.events.listen(myField, goog.editor.Field.EventType.BEFOREFOCUS,
                     goog.bind(this.showToolBar_, this, true));
  goog.events.listen(myField, goog.editor.Field.EventType.BLUR,
                     goog.bind(this.showToolBar_, this, false));

  this.showToolBar_(false);

  if (callback) {
    callback(this);
  }
};


lantern.wwedit.NotePad.prototype.showToolBar_ = function(show) {
  if (!show) {
    /* losing focus now; the contents need saving */
    this.updateNotePadValue_();
  }
  goog.style.showElement(this.notepadEditToolbar_, show);
};


lantern.wwedit.NotePad.prototype.updateNotePadValue_ = function() {
  var text = this.notepadField_.getCleanContents();
  var key = this.notepadId_;

  this.sendRequest('/notepad/update',
                   goog.bind(this.updatedNotePadValue_, this),
                   'POST',
                   'text=' + encodeURIComponent(text) + '&amp;' +
                   'key=' + encodeURIComponent(key) + '&amp;' +
                   'xsrf_token=' + xsrfToken);
};


lantern.wwedit.NotePad.prototype.updatedNotePadValue_ = function(
    requestId, result, opt_errMsg) {
  /* Nothing in particular... */
};


/**
 * Helper to send a request via XHR
 */
lantern.wwedit.NotePad.prototype.sendRequest = function(
    uri, callback, var_args) {
  var id = this.currentReequestId_++;
  var args = [id, uri, callback];
  var i;
  for (i = 2; i < arguments.length; i++)
    args.push(arguments[i]);
  this.xhr_.sendRequest.apply(this.xhr_, args);
};

/**
 * @override
 */
lantern.wwedit.NotePad.prototype.disposeInternal = function() {
  this.updateNotePadValue_();

  this.notepadCTEW_.dispose();
  this.notepadCTEW_ = null;
  this.notepadField_.dispose();
  this.notepadField_ = null;
  this.xhr_.dispose();
  this.xhr_ = null;
};

// Export for use in HTML.
goog.exportSymbol('lantern.wwedit.NotepadManager',
                  lantern.wwedit.NotepadManager);
