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
goog.provide('lantern.wwedit.RTEditorManager');

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
goog.require('goog.events.EventType');
goog.require('goog.style');

goog.require('lantern.DataProviderXhr');

/**
 * Keep track of all the HTMLEditors on a page, so that
 * we can get rid of them at once at the end.
 *
 * This is meant to be used as a base class.  enumeratEditorTargets
 * method should return an array of DOM element, each to be fed to
 * its newHTMLEditor method that return a subclass of HTMLEditor_.
 *
 * @constructor
 */
lantern.wwedit.HTMLEditorManager_ = function() {
  goog.Disposable.call(this);
  this.editors_ = [];
  this.populate(document);
};
goog.inherits(lantern.wwedit.HTMLEditorManager_, goog.Disposable);

lantern.wwedit.HTMLEditorManager_.prototype.populate = function(node) {
  var editors = this.enumerateEditorTargets(node);
  for (var i = 0; i < editors.length; i++) {
    this.editors_.push(this.newHTMLEditor(editors[i]));
  }
};

/**
 * @override
 */
lantern.wwedit.HTMLEditorManager_.prototype.disposeInternal = function() {
  for (var i = 0; i < this.editors_.length; i++) {
    this.editors_[i].dispose();
  }
  this.editors_ = null;
};

/**
 * Keep track of all the NotePad on a page, so that
 * we can get rid of them at once at the end
 */
lantern.wwedit.NotepadManager = function() {
  lantern.wwedit.HTMLEditorManager_.call(this);
};
goog.inherits(lantern.wwedit.NotepadManager, lantern.wwedit.HTMLEditorManager_);

/**
 * @override
 */
lantern.wwedit.NotepadManager.prototype.enumerateEditorTargets = function(root) {
  return goog.dom.findNodes(root,
                            function(child) {
                              return ((child.tagName == 'DIV') &&
                                      (child.className == 'notepad'));
                            });
};

lantern.wwedit.NotepadManager.prototype.newHTMLEditor = function(elem) {
  return new lantern.wwedit.NotePad(elem);
};

/**
 * Keep track of all the RichTextEditor on a page, so that
 * we can get rid of them at once at the end
 */
lantern.wwedit.RTEditorManager = function() {
  lantern.wwedit.HTMLEditorManager_.call(this);
};
goog.inherits(lantern.wwedit.RTEditorManager, lantern.wwedit.HTMLEditorManager_);

/**
 * @override
 */
lantern.wwedit.RTEditorManager.prototype.enumerateEditorTargets = function(root) {
  return goog.dom.findNodes(root,
                            function(child) {
                              return ((child.tagName == 'DIV') &&
                                      (child.className == 'rteditor'));
                            });
};

lantern.wwedit.RTEditorManager.prototype.newHTMLEditor = function(elem) {
  return new lantern.wwedit.RTEditor(elem);
};

/**
 * HTMLEditor_
 *
 * This is meant to be used as a base class.
 *
 * @param {Element} htmlEdit: a <div> element to be used as a Wysiwyg editor
 * @param {Element} htmlEditToolbar: a <div> element to be used as the toolbar
 *                  for the Wysiwyg editor
 * @constructor
 */
lantern.wwedit.HTMLEditor_ = function(htmlEdit, htmlEditToolbar) {
  goog.Disposable.call(this);
  if (!htmlEdit.id) {
    htmlEdit.id = 'wwedit' + lantern.wwedit.HTMLEditor_.IdSequence_++;
  }
  this.htmlEdit_ = htmlEdit;
  this.htmlField_ = new goog.editor.SeamlessField(this.htmlEdit_.id);
  this.htmlEditToolbar_ = htmlEditToolbar;
  this.xhr_ = new lantern.DataProviderXhr();
  this.currentRequestId_ = 0;
  this.eh_ = new goog.events.EventHandler(this);
};
goog.inherits(lantern.wwedit.HTMLEditor_, goog.Disposable);

lantern.wwedit.HTMLEditor_.IdSequence_ = 0;

lantern.wwedit.HTMLEditor_.prototype.setup = function(initial_text) {
  var myField = this.htmlField_;
  if (initial_text == "") {
    initial_text = "<br />";
  }
  myField.setHtml(false, initial_text);

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
      this.htmlEditToolbar_);

  // Hook the toolbar into the field.
  var myToolbarController =
      new goog.ui.editor.ToolbarController(myField, myToolbar);

  this.eh_.listen(myField, goog.editor.Field.EventType.BEFOREFOCUS,
                  goog.bind(this.showToolBar_, this, true));
  this.eh_.listen(myField, goog.editor.Field.EventType.BLUR,
                  goog.bind(this.showToolBar_, this, false));
};

lantern.wwedit.HTMLEditor_.prototype.showToolBar_ = function(show) {
  goog.style.showElement(this.htmlEditToolbar_, show);
};

/**
 * NotePad - an area on the page that student can scribble per-user notes
 * @constructor
 */
lantern.wwedit.NotePad = function(node) {
  var divEdit = goog.dom.findNode(node,
                                  function(child) {
                                    return ((child.tagName == 'DIV') &&
                                            (child.className == 'googedit'));
                                  });
  var divTB = goog.dom.findNode(node,
                                function(child) {
                                  return ((child.tagName == 'DIV') &&
                                          (child.className == 'edittb'));
                                });
  lantern.wwedit.HTMLEditor_.call(this, divEdit, divTB);
  this.htmlCTEW_ = new goog.editor.ClickToEditWrapper(this.htmlField_);
  this.showToolBar_(false);

  var notepadKey = goog.dom.findNode(node,
                                     function(child) {
                                       return ((child.tagName == 'INPUT') &&
                                               (child.name == 'key'));
                                     });
  this.notepadId_ = notepadKey.value;
  this.sendRequest('/notepad/get',
                   goog.bind(this.receiveNotePadValue_, this),
                   'POST',
                   'key=' + encodeURIComponent(this.notepadId_) + '&amp;' +
                   'xsrf_token=' + xsrfToken);
};
goog.inherits(lantern.wwedit.NotePad, lantern.wwedit.HTMLEditor_);

/**
 * @private
 */
lantern.wwedit.NotePad.prototype.receiveNotePadValue_ = function(
    requestId, result, opt_errMsg) {
  text = (result ? result.text : "");
  this.setup(text);
};


lantern.wwedit.NotePad.prototype.showToolBar_ = function(show) {
  if (!show) {
    /* losing focus now; the contents need saving */
    this.updateNotePadValue_();
  }
  lantern.wwedit.HTMLEditor_.prototype.showToolBar_.call(this, show);
};


lantern.wwedit.NotePad.prototype.updateNotePadValue_ = function() {
  var text = this.htmlField_.getCleanContents();
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
 * RTEditor
 * @constructor
 */
lantern.wwedit.RTEditor = function(node) {
  var divEdit = node;
  var divTB = goog.dom.findNode(node.parentNode,
                                function(child) {
                                  return ((child.tagName == 'DIV') &&
                                          (child.className == 'edittb'));
                                });
  lantern.wwedit.HTMLEditor_.call(this, divEdit, divTB);
  this.htmlField_.makeEditable();

  var divCB = goog.dom.findNode(node.parentNode,
                                function(child) {
                                  return ((child.tagName == 'DIV') &&
                                          (child.className == 'controlbar'));
                                });
  this.toggleHTMLButton_ = goog.dom.findNode(node.parentNode,
                                             function(child) {
                                               return ((child.tagName == 'INPUT') &&
                                                       (child.className == 'toggleHTML'));
                                             });
  this.toggleHTMLButton_.value = 'Edit HTML';
  this.eh_.listen(this.toggleHTMLButton_, goog.events.EventType.CLICK,
                  goog.bind(this.toggleHTMLEdit, this));
  divCB.appendChild(this.toggleHTMLButton_);
  this.teSource_ = goog.dom.findNode(node.parentNode.parentNode,
                                     function(child) {
                                       return ((child.tagName == 'TEXTAREA') &&
                                               (child.className == 'value'));
                                     });
  goog.style.showElement(this.teSource_, false);
  goog.style.showElement(node, true);
  this.setup(this.teSource_.value);
  this.showToolBar_(true);
};
goog.inherits(lantern.wwedit.RTEditor, lantern.wwedit.HTMLEditor_);


lantern.wwedit.RTEditor.prototype.showToolBar_ = function(show) {
  if (!show) {
    this.updateTESource();
  }
};


lantern.wwedit.RTEditor.prototype.updateTESource = function() {
  this.teSource_.value = this.htmlField_.getCleanContents();
};


lantern.wwedit.RTEditor.prototype.toggleHTMLEdit = function() {
  var b = this.toggleHTMLButton_;
  if (b.value == 'Edit HTML') {
    this.updateTESource();
    goog.style.showElement(this.htmlEditToolbar_, false);
    goog.style.showElement(this.htmlEdit_, false);
    goog.style.showElement(this.teSource_, true);
    b.value = 'Edit Rich Text';
  } else {
    this.htmlField_.setHtml(false, this.teSource_.value);
    goog.style.showElement(this.htmlEditToolbar_, true);
    goog.style.showElement(this.htmlEdit_, true);
    goog.style.showElement(this.teSource_, false);
    b.value = 'Edit HTML';
  }
};


/**
 * Helper to send a request via XHR
 */
lantern.wwedit.NotePad.prototype.sendRequest = function(
    uri, callback, var_args) {
  var id = this.currentRequestId_++;
  var args = [id, uri, callback];
  var i;
  for (i = 2; i < arguments.length; i++)
    args.push(arguments[i]);
  this.xhr_.sendRequest.apply(this.xhr_, args);
};

/**
 * @override
 */
lantern.wwedit.HTMLEditor_.prototype.disposeInternal = function() {
  this.htmlField_.dispose();
  this.htmlField_ = null;
  this.xhr_.dispose();
  this.xhr_ = null;
  this.eh_.dispose();
  this.eh_ = null;
}

lantern.wwedit.NotePad.prototype.disposeInternal = function() {
  this.updateNotePadValue_();
  lantern.wwedit.HTMLEditor_.disposeInternal.call(this);
  this.htmlCTEW_.dispose();
  this.htmlCTEW_ = null;
};

// Export for use in HTML.
goog.exportSymbol('lantern.wwedit.NotepadManager',
                  lantern.wwedit.NotepadManager);
goog.exportSymbol('lantern.wwedit.RTEditorManager',
                  lantern.wwedit.RTEditorManager);
