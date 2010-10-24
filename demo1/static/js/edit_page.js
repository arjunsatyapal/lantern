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
 * @fileoverview This module contains code for the edit page.
 *
 * <ul>
 *  <li>DragDrop is a simple wrapper around Closure's DragListGroup, providing
 *    a method for getting the drag handle for each editable item.
 *
 *  <li>LinkPicker presents the dialog boxes for the user to select Doc links
 *    and widget links. It manages the Async calls to the server to get
 *    suggestion lists for the dialog boxes.
 *    TODO(vchen): Be more sophisticated about suggestions. May need to
 *    separate out into own file.
 *
 *  <li>EditPage is the overall manager of activity on the page. It initializes
 *    DragDrop and LinkPicker. The constructor expects to get a map of
 *    HTML templates for each type of content. These templates should be
 *    identical to those used by the server via Django templating. Otherwise,
 *    dynamically added content may not behave the same as the initially loaded
 *    ones.
 * </ul>
 */

goog.provide('lantern.edit.DragDrop');
goog.provide('lantern.edit.EditPage');
goog.provide('lantern.edit.LinkPicker');

goog.require('goog.Disposable');
goog.require('goog.dom');
goog.require('goog.events');
goog.require('goog.events.EventHandler');
goog.require('goog.dom.classes');
goog.require('goog.fx.DragListDirection');
goog.require('goog.fx.DragListGroup');
goog.require('goog.ui.Dialog');
goog.require('goog.ui.Dialog.EventType');

goog.require('lantern.DataProviderXhr');

/**
 * DragDrop manager for a list of items.
 *
 * Call reset() and init() when items are added or removed from the container
 * DIV. The calls are split to allow reset() to be called before removing
 * the underlying attached list items from the DOM.
 *
 * @param {string} id The string ID of the DIV that includes the draggable
 *     list of items. The immediate children of the DIV will be the draggable
 *     items. Each child must have an element using class="drag-handle" that
 *     will become the drag handle.
 *
 * @constructor
 * @extends {goog.Disposable}
 */
lantern.edit.DragDrop = function(id) {
  goog.Disposable.call(this);

  /**
   * The ID of the container DIV.
   * @type string
   * @private
   */
  this.id_ = id;

  /**
   * The current DragListGroup. A new is created by init().
   * @type goog.fx.DragListGroup
   * @private
   */
  this.dragListGroup_ = null;

  this.init();
};
goog.inherits(lantern.edit.DragDrop, goog.Disposable);


/**
 * Class name for the drag handle. It is expected that each draggable item
 * contains an element marked with this class.
 * @type string
 * @private
 */
lantern.edit.DragDrop.CLASS_DRAG_HANDLE_ = 'drag-handle';


/**
 * Initializes the handler, resetting the current one, if needed.
 * Creates a new DragListGroup in order to bind to all current children of
 * the container.
 *
 * <p>This method needs to be called after content has been added or removed.
 */
lantern.edit.DragDrop.prototype.init = function() {
  if (this.dragListGroup_) {
    this.reset();
  }
  this.dragListGroup_ = new goog.fx.DragListGroup();
  this.dragListGroup_.addDragList(
      goog.dom.getElement(this.id_),
      goog.fx.DragListDirection.UP);

  this.dragListGroup_.setFunctionToGetHandleForDragItem(
      goog.bind(this.getHandle, this));
  this.dragListGroup_.setDraggerElClass('drag-opacity');
  this.dragListGroup_.init();
};


/**
 * Resets/Disposes the handler. Call init() again to set up handlers.
 * Call reset() before removing elements from the page and init()
 * to set up the handlers after removal.
 */
lantern.edit.DragDrop.prototype.reset = function() {
  this.dragListGroup_.dispose();
  this.dragListGroup_ = null;
};


/**
 * Finds the drag handle for the specified item.
 *
 * @param {Element} item DIV in which to find a drag handle.
 */
lantern.edit.DragDrop.prototype.getHandle = function(item) {
  var handles = goog.dom.getElementsByTagNameAndClass(
      'div', lantern.edit.DragDrop.CLASS_DRAG_HANDLE_, item);
  if ((handles)) {
    return handles[0];
  }
  return null;
};


/**
 * @override
 */
lantern.edit.DragDrop.prototype.disposeInternal = function() {
  this.reset();
};

// ------------------------------

/**
 * Link-picker manager. It encapsulates the XHR and building/display of the
 * pop-up dialog offering the suggestions.
 *
 * <ul>The public methods are:
 *  <li>requestDocLinkList() gets a list of Doc Link recommendations.
 *  <li>requestWidgetLinkList() gets a list of Widget Link recommendations.
 * </ul>
 *
 * Each requires a callback to be called when the user makes a choice. If the
 * user dismisses the dialog without a choice, the callback will never be
 * called. Each callback has a different signature.
 *
 * TODO(vchen): Implement better recommendations. Current offers all links.
 *
 * @constructor
 * @extends {goog.Disposable}
 */
lantern.edit.LinkPicker = function() {
  goog.Disposable.call(this);

  /**
   * Dialog box used to ask for a link selection. Contents will be rebuilt.
   * @type goog.ui.Dialog
   * @private
   */
  this.dialog_ = new goog.ui.Dialog(null, true);  // modal

  /**
   * Manager for XHR requests.
   * @type {lantern.DataProviderXhr}
   * @private
   */
  this.xhr_ = new lantern.DataProviderXhr();

  /**
   * Event handler helper.
   * @type {goog.events.EventHandler}
   * @private
   */
  this.eh_ = new goog.events.EventHandler(this);

  // Initialize
  goog.dom.classes.add(this.dialog_.getContentElement(), 'linkpicker');
  this.dialog_.setTitle('Link Picker');

  // initial paging index and entries per page
  this.startAt_ = 0;
  this.count_ = 8;
};
goog.inherits(lantern.edit.LinkPicker, goog.Disposable);


/**
 * Unique id for each request.
 * @type number
 * @private
 */
lantern.edit.LinkPicker.currentRequestId_ = 0;


/**
 * Helper to send a request via XHR
 */
lantern.edit.LinkPicker.prototype.sendRequest = function(
    uri, callback, opt_method, opt_content) {
  this.xhr_.sendRequest(
      undefined /* autogen ID */, callback, opt_method, opt_content);
}


/**
 * Activate the new doc link picker that shows:
 *
 * - A control to create a new document and link to it immediately;
 * - A control to get a list of existing document and pick from it.
 *
 * The latter limits the size of the list and allows:
 *
 * - Paging control by prev/next;
 * - Narrowing the selection by head match;
 *
 * <p>After selection, the callback is called. Note that the callback will not
 * be called if the user dismisses the dialog without selection.
 *
 * @param {Function} docLinkCallback will be called after selection. The
 *     signature is:
 *       docLinkCallback(trunkId, docId, title);
 */
lantern.edit.LinkPicker.prototype.activateDocLinkList = function(
    docLinkCallback) {
  var handler = new goog.events.EventHandler(this);
  var row;

  var newDocName = goog.dom.createDom('input', { 'type': 'text' });
  var newDocButton = goog.dom.createDom('input', {
      'type': 'button', 'value': 'New Document'});
  this.newDocRow_ = goog.dom.createDom('tr');
  this.newDocRow_.appendChild(goog.dom.createDom('td', null, newDocName));
  this.newDocRow_.appendChild(goog.dom.createDom('td', null, newDocButton));

  this.dialogContent_ = goog.dom.createDom('table', {width: '100%'});
  this.dialogContent_.appendChild(this.newDocRow_);
  handler.listen(newDocButton, goog.events.EventType.CLICK,
                 goog.bind(this.requestNewDoc_, this,
                           docLinkCallback, newDocName));

  var limitDocString = goog.dom.createDom('input', { 'type': 'text' });
  var limitDocButton = goog.dom.createDom('input', {
      'type': 'button', 'value': 'Search'});
  this.limitDocRow_ = goog.dom.createDom('tr');
  this.limitDocRow_.appendChild(goog.dom.createDom('td', null, limitDocString));
  this.limitDocRow_.appendChild(goog.dom.createDom('td', null, limitDocButton));
  this.dialogContent_.appendChild(this.limitDocRow_);

  handler.listen(limitDocButton, goog.events.EventType.CLICK,
                 goog.bind(this.updateDocLinkList_, this,
                           docLinkCallback, limitDocString, 0));

  handler.listen(limitDocString, goog.events.EventType.KEYUP,
                 goog.bind(this.updateDocLinkList_, this,
                           docLinkCallback, limitDocString, 0));

  var container = this.dialog_.getContentElement();
  goog.dom.removeChildren(container);
  goog.dom.append(container, this.dialogContent_);
  this.limitDocString_ = limitDocString;

  this.eh_.listenOnce(this.dialog_, goog.ui.Dialog.EventType.AFTER_HIDE,
                      handler.dispose, false, handler);
  this.dialog_.setVisible(true);

  this.updateDocLinkList_(docLinkCallback, limitDocString, 0);
};


/**
 * Make an asynchronous request to find small number of documents
 * starting at startAt whose name begins with contents of limitDocString.
 */
lantern.edit.LinkPicker.prototype.updateDocLinkList_ = function(
    docLinkCallback, limitDocString, startAt) {
  if (startAt < 0) {
    startAt = 0;
  }

  /* TODO: perhaps use goog.uri.Uri() */
  var uri = '/getListAjax?s=' + encodeURIComponent(startAt);
  uri = uri + "&amp;c=" + this.count_;
  if (limitDocString.value != "") {
    uri = uri +"&amp;q=" + encodeURIComponent(limitDocString.value);
  }
  this.sendRequest(uri,
                   goog.bind(this.processDocLinkList_, this, docLinkCallback));
};


/**
 * Requests a list of widget links for the user to select. It issues an XHR call
 * to get the suggestions, then presents a dialog for the user to make a
 * selection.
 *
 * <p>After selection, the callback is called. Note that the callback will not
 * be called if the user dismisses the dialog without selection.
 *
 * @param {Function} widgetLinkCallback will be called after selection:
 *     widgetLinkCallback(widgetLink, isShared);
 */
lantern.edit.LinkPicker.prototype.requestWidgetList = function(
    widgetLinkCallback) {
  this.sendRequest('/quiz/widgetList',
                   goog.bind(this.processWidgetList_, this, widgetLinkCallback));
};


/**
 * Processes a list of doc links to display in the dialog box.
 * This is called when the XHR response arrives.
 *
 * @param {Function} docLinkCallback The callback to call after the user makes
 *     a selection.
 *       docLinkCallback(trunkId, docId, title);
 * @param {number} requestId The associated request ID.
 * @param {Object} result The JSON decoded XHR response.
 * @param {string} opt_errMsg Optional error message that resulted from the XHR
 *     call.
 */
lantern.edit.LinkPicker.prototype.processDocLinkList_ = function(
    docLinkCallback, requestId, result, opt_errMsg) {
  var obj = result;
  var container = this.dialog_.getContentElement();
  var dialogContent = this.dialogContent_;

  var newDocRow = this.newDocRow_;
  var limitDocRow = this.limitDocRow_;
  var limitDocString = this.limitDocString_;

  goog.dom.removeChildren(dialogContent);
  dialogContent.appendChild(newDocRow);
  dialogContent.appendChild(limitDocRow);

  this.startAt_ = obj.startAt + 0;

  var docList = obj.doc_list;

  // Local handler for all the links that we'd like to clean up.
  var handler = new goog.events.EventHandler(this);

  // Construct a selector link and preview button for each item
  for (var i = 0, n = docList.length; i < n; i++) {
    var docItem = docList[i];
    var docLink = goog.dom.createDom('a', null, docItem.doc_title);

    handler.listen(docLink, goog.events.EventType.CLICK,
                   goog.partial(docLinkCallback, docItem.trunk_id,
                                docItem.doc_id, docItem.doc_title));

    var preview = goog.dom.createDom('input', {
        'type': 'button', 'value': 'Preview'});

    var uri = '/view?trunk_id=' + docItem.trunk_id
        + '&doc_id=' + docItem.doc_id
        + '&absolute=True';

    handler.listen(preview, goog.events.EventType.CLICK,
                   goog.bind(window.open, window, uri));

    var row = goog.dom.createDom('tr');
    row.appendChild(goog.dom.createDom('td', null, docLink));
    row.appendChild(goog.dom.createDom('td', null, preview));
    dialogContent.appendChild(row);
  }

  // Append prev and next control
  var prevButton = goog.dom.createDom('input', {
      'type': 'button', 'value': 'Prev'});
  var nextButton = goog.dom.createDom('input', {
      'type': 'button', 'value': 'Next'});
  var row = goog.dom.createDom('tr');
  row.appendChild(goog.dom.createDom('td', null, prevButton));
  row.appendChild(goog.dom.createDom('td', null, nextButton));
  dialogContent.appendChild(row);

  if (this.startAt_ == 0) {
    prevButton.disabled = true;
  } else {
    handler.listen(prevButton, goog.events.EventType.CLICK,
                   goog.bind(this.updateDocLinkList_, this,
                             docLinkCallback, limitDocString,
                             this.startAt_ - this.count_));
  }

  if (obj.atEnd) {
    nextButton.disabled = true;
  } else {
    handler.listen(nextButton, goog.events.EventType.CLICK,
                   goog.bind(this.updateDocLinkList_, this,
                             docLinkCallback, limitDocString,
                             this.startAt_ + this.count_));
  }

  limitDocString.focus();

  // Make sure all the event handlers are cleaned up when the dialog is
  // dismissed.
  this.eh_.listenOnce(this.dialog_, goog.ui.Dialog.EventType.AFTER_HIDE,
                      handler.dispose, false, handler);
  this.dialog_.setVisible(true);
};


/**
 * Request one new stub document to be created by issuing an XHR call;
 * the server responds with the usual trunk/doc-id/title tuple when done,
 * and we relay them to the caller via docLinkCallback().
 */
lantern.edit.LinkPicker.prototype.requestNewDoc_ = function(
    docLinkCallback, newdocName) {
  var title = newdocName.value;
  this.sendRequest('/newDocumentAjax',
                   goog.bind(this.processNewDoc_, this, docLinkCallback),
                   'POST', 'title=' + encodeURIComponent(title));
}


/**
 * When the XHR response to create a new document arrives, this
 * is called and adds the document link.
 *
 * @param {Function} docLinkCallback The callback to call after the user makes
 *     a selection.
 *       docLinkCallback(trunkId, docId, title);
 * @param {number} requestId The associated request ID.
 * @param {Object} result The JSON decoded XHR response.
 * @param {string} opt_errMsg Optional error message that resulted from the XHR
 *     call.
 */
lantern.edit.LinkPicker.prototype.processNewDoc_ = function(
    docLinkCallback, requestId, result, opt_errMsg) {
  docLinkCallback(result.trunk_id, result.doc_id, result.doc_title);
}


/**
 * Processes a list of widget links to display in the dialog box.
 * This is called when the XHR response arrives.
 *
 * @param {Function} widgetLinkCallback The callback to call after the user
 *     makes a selection.
 *       widgetLinkCallback(link, isShared);
 * @param {number} requestId The associated request ID.
 * @param {Object} result The JSON decoded XHR response.
 * @param {string} opt_errMsg Optional error message that resulted from the XHR
 *     call.
 */
lantern.edit.LinkPicker.prototype.processWidgetList_ = function(
    widgetLinkCallback, requestId, result, opt_errMsg) {
  var obj = result;
  var dialogContent = goog.dom.createDom(
      'table', {width: '100%'});
  var widgetList = obj.widget_list;

  // Local handler for all the links that we'd like to clean up.
  var handler = new goog.events.EventHandler(this);

  // Construct a selector for each item.
  for (var i = 0, n = widgetList.length; i < n; i++) {
    var widgetItem = widgetList[i];
    var widgetLink = goog.dom.createDom('a', null, widgetItem.title);

    handler.listen(widgetLink, goog.events.EventType.CLICK,
                   goog.partial(widgetLinkCallback, widgetItem.link));

    var row = goog.dom.createDom(
        'tr', null,
        goog.dom.createDom('td', null, widgetLink));
    dialogContent.appendChild(row);
  }
  // Replace content of dialog.
  var container = this.dialog_.getContentElement();
  goog.dom.removeChildren(container);
  goog.dom.append(container, dialogContent);

  // Make sure all the event handlers are cleaned up when the dialog is
  // dismissed.
  this.eh_.listenOnce(this.dialog_, goog.ui.Dialog.EventType.AFTER_HIDE,
                      handler.dispose, false, handler);
  this.dialog_.setVisible(true);
};


/**
 * Hides/dismisses the dialog.
 */
lantern.edit.LinkPicker.prototype.hide = function() {
  this.dialog_.setVisible(false);
};


/**
 * @override
 */
lantern.edit.LinkPicker.prototype.disposeInternal = function() {
  goog.dom.removeChildren(this.dialog_.getContentElement());
  this.eh_.dispose();
  this.xhr_.dispose();
  this.dialog_.dispose();

  this.eh_ = null;
  this.xhr_ = null;
  this.dialog_ = null;
};


// ------------------------------

/**
 * Wraps functionality needed by the Edit page. It attaches actions to the
 * edit menu and initializes the DragDrop and LinkPicker.
 *
 * <p>This class also contains the methods that adds and removes content from
 * the page.
 *
 * <p>NOTE: For now, the delete buttons are expecting a top-level method
 * called deleteRow(). Do the following to bind it to this class.
 *
 *   var editPage = new lantern.edit.EditPage('doc_contents', templates);
 *   var deleteRow = goog.bind(editPage.deleteRow, editPage);
 *
 * @param {string} contentId The id of the DIV that holds the doc contents.
 *     The direct children of this DIV will be used for drag-drop.
 * @param {Object} templates A map of content type to a template string
 *     containing  the HTML template to insert into the page. The keys of the
 *     map are expected to be the values of the option buttons.
 *       'rich_text', 'doc_link', 'video', 'quiz', 'widget', 'notepad'
 *
 * @constructor
 * @extends {goog.Disposable}
 */
lantern.edit.EditPage = function(contentId, templates) {
  goog.Disposable.call(this);

  this.contentId_ = contentId;
  this.templates_ = templates;

  /**
   * Drag and drop.
   * @type lantern.edit.DragDrop
   * @private
   */
  this.dragDrop_ = new lantern.edit.DragDrop(contentId);

  /**
   * Link picker.
   * @type lantern.edit.LinkPicker
   * @private
   */
  this.linkPicker_ = new lantern.edit.LinkPicker();

  /**
   * Event handler helper.
   * @type {goog.events.EventHandler}
   * @private
   */
  this.eh_ = new goog.events.EventHandler(this);

  // Initialize by attaching to the edit menu.
  var editMenu = goog.dom.getElement('object_type');
  this.eh_.listen(editMenu, goog.events.EventType.CHANGE,
                  this.handleAddItem_)
};
goog.inherits(lantern.edit.EditPage, goog.Disposable);


/**
 * Unique ID for creating new content.
 * @type number
 * @private
 */
lantern.edit.EditPage.uniqueId_ = 0;


/**
 * Deletes the specified content. This must be bound to a top-level method
 * using syntax such as:
 *
 *  var deleteRow = goog.bind(editPage.deleteRow, editPage);
 *
 * @param {string} elemId The ID of the row to delete.
 */
lantern.edit.EditPage.prototype.deleteRow = function(elemId) {
  this.dragDrop_.reset();
  var elem = goog.dom.getElement(elemId);
  if (elem) {
    goog.dom.removeChildren(elem);
    goog.dom.removeNode(elem);
    this.dragDrop_.init();
  }
};


/**
 * Handler for the Add Menu. It directly inserts selected content or invokes
 * the LinkPicker.
 * @private
 */
lantern.edit.EditPage.prototype.handleAddItem_ = function(e) {
  var optionElem = e.target;
  var option = optionElem.options[optionElem.selectedIndex];
  optionElem.selectedIndex = 0;

  if (option.value == 'doc_link'){
    this.linkPicker_.activateDocLinkList(
        goog.bind(this.addDocLink_, this));
  } else if (option.value == 'quiz'){
    this.linkPicker_.requestWidgetList(
        goog.bind(this.addWidgetLink_, this));
  } else {
    this.addContent_(option.value);
  }
};


/**
 * Returns a unique object ID to use. It will be 'content_row' + num.
 */
lantern.edit.EditPage.prototype.nextObjectId_ = function() {
  var counter = lantern.edit.EditPage.uniqueId_++;
  var objectId = 'content_row' + counter;
  return objectId;
};


/**
 * Adds a Doc Link to the page. This will be called after the user selects
 * an entry from the LinkPicker dialog box.
 */
lantern.edit.EditPage.prototype.addDocLink_ = function(
    trunkId, docId, title) {
  var objectId = this.nextObjectId_();
  var templateText = this.templates_['preamble'] + this.templates_['doc_link'];
  templateText = templateText.replace('\{\{object.key}}', objectId);
  templateText = templateText.replace('\{\{object.trunk_ref.key}}', trunkId);
  templateText = templateText.replace('\{\{object.doc_ref.key}}', docId);
  templateText = templateText.replace('\{\{object.doc_ref.trunk_tip.title}}', title);

  this.addContentToPage_(objectId, templateText);
  this.linkPicker_.hide();
};


/**
 * Adds a Widget Link to the page. This will be called after the user selects
 * an entry from the LinkPicker dialog box.
 *
 * @param {string} link The URI of the widget.
 * @param {boolean} isShared Whether the widget should be shared between
 *     different pages.
 */
lantern.edit.EditPage.prototype.addWidgetLink_ = function(link, isShared) {
  var objectId = this.nextObjectId_();
  var templateText = this.templates_['preamble'] + this.templates_['widget'];
  templateText = templateText.replace('\{\{object.key}}', objectId);
  templateText = templateText.replace('\{\{object.widget_url}}', link);
  templateText = templateText.replace('\{\{object.title}}', '');
  templateText = templateText.replace('\{\{object.width}}', '100%');
  templateText = templateText.replace('\{\{object.height}}', '400px');
  templateText = templateText.replace('\{\{object.is_shared}}',
                                      isShared ? 'True' : 'False');

  this.addContentToPage_(objectId, templateText);
  this.linkPicker_.hide();
};


/**
 * Adds specified content type that does not require the LinkPicker.
 */
lantern.edit.EditPage.prototype.addContent_ = function(contentType) {
  var objectId = this.nextObjectId_();
  var templateText = this.templates_['preamble'] + this.templates_[contentType];

  if (contentType == 'rich_text') {
    templateText = templateText.replace('\{\{object.key}}', objectId);
    templateText = templateText.replace('\{\{object.data}}', '');

  } else if (contentType == 'video') {
    templateText = templateText.replace('\{\{object.key}}', objectId);
    templateText = templateText.replace('\{\{object.video_id}}', '');
    templateText = templateText.replace('\{\{object.title}}', '');
    templateText = templateText.replace('\{\{object.width}}', '600px');
    templateText = templateText.replace('\{\{object.height}}', '300px');

  } else if (contentType == 'quiz') {
    // Do not insert now, wait for dialog selection.
    templateText = null;
  } else if (contentType == 'widget') {
    templateText = templateText.replace('\{\{object.key}}', objectId);
    templateText = templateText.replace('\{\{object.widget_url}}', '');
    templateText = templateText.replace('\{\{object.title}}', '');
    templateText = templateText.replace('\{\{object.width}}', '100%');
    templateText = templateText.replace('\{\{object.height}}', '400px');
  } else if (contentType == 'notepad') {
    templateText = templateText.replace('\{\{object.key}}', objectId);
    templateText = templateText.replace('\{\{object.notepad}}', '');
  } else {
    alert('Unexpected content type: ' + contentType);
    return;
  }
  if (templateText) {
    this.addContentToPage_(objectId, templateText);
  }
};


/**
 * Worker method that adds the HTML to the page, appending it to the end
 * of the container.
 */
lantern.edit.EditPage.prototype.addContentToPage_ = function(objectId, html) {
  var newRow = goog.dom.createDom('div',
      {'id': objectId,
       'class': 'doc_edit'});
  newRow.innerHTML = html;

  var el1 = goog.dom.getElement(this.contentId_);
  el1.appendChild(newRow);
  // Reinitialize drag drop after changing contents.
  this.dragDrop_.init();
};


/**
 * @override
 */
lantern.edit.EditPage.prototype.disposeInternal = function() {
  this.dragDrop_.dispose();
  this.linkPicker_.dispose();
  this.eh_.dispose();

  this.dialogContent_ = null;
  this.newDocRow_ = null;
  this.limitDocRow_ = null;
  this.limitDocString_ = null;

  this.dragDrop_ = null;
  this.linkPicker_ = null;
  this.eh_ = null;
};


// Export for use in HTML.
goog.exportSymbol('lantern.edit.EditPage',
                  lantern.edit.EditPage);
goog.exportProperty(lantern.edit.EditPage.prototype, 'deleteRow',
                    lantern.edit.EditPage.prototype.deleteRow);
goog.exportProperty(lantern.edit.EditPage.prototype, 'dispose',
                    lantern.edit.EditPage.prototype.dispose);

goog.exportSymbol('goog.bind',
                  goog.bind);
goog.exportSymbol('goog.events.listenOnce',
                  goog.events.listenOnce);
