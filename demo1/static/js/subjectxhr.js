// Copyright 2010 Google Inc. All Rights Reserved.
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
 * @fileoverview SubjectProvider that uses XHR to load subjects from the
 *     server.
 */

goog.provide('lantern.subject.SubjectProviderXhr');

goog.require('goog.debug.Logger');
goog.require('goog.events.EventHandler');
goog.require('goog.events.EventTarget');
goog.require('goog.net.XhrManager');
goog.require('goog.structs.Map');
goog.require('goog.Uri');

goog.require('lantern.subject.SubjectProvider');


/**
 * SubjectProvider that loads data via XHR.  It uses the following URI:
 *
 *  /subjects/ Request all root subjects
 *  /subjects/subj1 Request descendents of subj1
 *
 * @param {string} opt_xhrUri Optional base URI.  If not specified, the default
 *     will be used ("/subjects/").
 * @constructor
 * @extends {lantern.subject.SubjectProvider}
 */
lantern.subject.SubjectProviderXhr = function(opt_xhrUri) {
  lantern.subject.SubjectProvider.call(this);

  /**
   * Base URI for XHR queries.
   * @type {string}
   * @private
   */
  this.xhrUri_ = opt_xhrUri;

  /**
   * Manager for XHR requests.
   * @type {goog.net.XhrManager}
   * @private
   */
  this.xhr_ = new goog.net.XhrManager(
      2 /* opt_maxRetries */,
      undefined /* opt_headers */,
      undefined /* opt_minCount */,
      undefined /* opt_maxCount */,
      10000 /* opt_timeoutInterval ms */
      );

  /**
   * Map that holds in-flight requests to avoid duplicates.
   * @type {goog.structs.Map}
   * @private
   */
  this.currentRequests_ = new goog.structs.Map()

  /**
   * Event handler helper.
   * @type {goog.events.EventHandler}
   * @private
   */
  this.eh_ = new goog.events.EventHandler(this);

  // Set up event handlers
  this.eh_.listen(this.xhr_, goog.net.EventType.SUCCESS,
                  this.onRemoteSuccess_);
  this.eh_.listen(this.xhr_,
                  [goog.net.EventType.ERROR,
                   goog.net.EventType.ABORT,
                   goog.net.EventType.TIMEOUT], this.onRemoteError_);
};
goog.inherits(lantern.subject.SubjectProviderXhr,
              lantern.subject.SubjectProvider);

/**
 * Default priority for XhrManager requests.
 * @type {number}
 * @private
 */
lantern.subject.SubjectProviderXhr.DEFAULT_XHR_PRIORITY_ = 100;


/**
 * Default base URL for XHR requests.
 * @type {string}
 * @private
 */
lantern.subject.SubjectProviderXhr.DEFAULT_XHR_URI_ = '/subjects/';


/**
 * Returns the URI to use for XHR.
 * @param {string?} id The ID of the subject to retrieve. If null, load root
 *     subjects.
 * @return {goog.Uri}
 */
lantern.subject.SubjectProviderXhr.prototype.getXhrUri_ = function(id) {
  var uri = new goog.Uri(
      (this.xhrUri_
           ? this.xhrUri_
           : lantern.subject.SubjectProviderXhr.DEFAULT_XHR_URI_)
      + (id ? id : ''));
  return uri;
}


/**
 * @inheritDoc
 * Overrides to perform async load of subjects.
 */
lantern.subject.SubjectProviderXhr.prototype.loadSubjects = function(id) {
  var uri = this.getXhrUri_(id);
  this.sendRequest_(id, uri, goog.bind(this.onDataReady_, this));
};


/**
 * Adds subjects from the JSON result to the specified model. Recursive.
 *
 * @param {lantern.subject.SubjectTreeModel} treeModel The model to which to
 *     add subjects.
 * @param {string} parentId The parent ID to which the results belong.  If null,
 *     it means the root of the taxonomy.
 * @param {Object} result The JSON result, expressed as a mapping from
 *     subject ID to a list of subject items of the form:
 *        {i: id, n: name, l: isLeaf}
 */
lantern.subject.SubjectProviderXhr.prototype.addSubjects_ = function(
    treeModel, parentId, result) {
  var subjects = result[parentId ? parentId : 'root'];
  if (subjects) {
    var numItems = subjects.length;
    for (var i = 0; i < numItems; ++i) {
      var s = subjects[i];
      var subject = new lantern.subject.SubjectItem(s.i, s.n, s.l);
      treeModel.addSubject(subject, (parentId == 'root') ? null : parentId);

      // Add children
      this.addSubjects_(treeModel, s.i, result);
    }
  }
};


/**
 * Merge the JSON results into underlying tree model.
 *
 * The current implementation simply builds a new model, but preserves
 * the hierarchy from the specified parentId to the root to make <BACK work.
 *
 * @param {string} id The parent ID to which the results belong. If null,
 *     it means the root of the taxonomy.
 * @param {Object} result The JSON result, expressed as a mapping from
 *     subject ID to a list of subject items of the form:
 *        {i: id, n: name, l: isLeaf}
 */
lantern.subject.SubjectProviderXhr.prototype.mergeSubjects_ = function(
    id, result) {
  var newTreeModel = new lantern.subject.SubjectTreeModel();

  // Preserve the path to the root.
  var tmpId = id;
  while (tmpId) {
    var subject = this.treeModel_.getSubject(tmpId);
    var parent = this.treeModel_.getParent(tmpId);
    var parentId = parent ? parent.id : null;
    if (subject) {
      newTreeModel.addSubject(subject, parentId);
    }
    tmpId = parentId;
  }
  // Add new results and replace the underlying model.
  this.addSubjects_(newTreeModel, id, result);
  this.treeModel_.clear();
  this.treeModel_ = newTreeModel;
};


/**
 * Event handler for new data to merge results into the underlying tree
 * model. Dispatches the DATA_READY event on completion.
 *
 * TODO(vchen): Determine what to do no errors.
 *
 * @param {string} id The parent ID to which the results belong. If null,
 *     it means the root of the taxonomy.
 * @param {Object} result The JSON result, expressed as a mapping from
 *     subject ID to a list of subject items of the form:
 *        {i: id, n: name, l: isLeaf}
 * @param {string} opt_errMsg Possible error message from the request handler.
 */
lantern.subject.SubjectProviderXhr.prototype.onDataReady_ = function(
    id, result, opt_errMsg) {
  this.mergeSubjects_(id, result);
  this.dispatchEvent(lantern.subject.SubjectProvider.EventType.DATA_READY);
};


/**
 * @inheritDoc
 */
lantern.subject.SubjectProviderXhr.prototype.disposeInternal = function() {
  lantern.subject.SubjectProviderXhr.superClass_.disposeInternal.call(this);

  this.eh_.dispose();
  this.eh_ = null;
  this.currentRequests_ = null;
};


/**
 * Issue XHR/Json request.
 *
 * @param {string} id The request id. If a request is already in progress,
 *     an error is thrown.
 * @param {string|goog.Uri} uri The request URI.
 * @param {Function} opt_callback Callback function when the request is
 *     complete.  The callback has the signature:
 *      callback(id, result, opt_errorMsg)
 *     where opt_errorMsg is not passed in if there were no errors.
 * @throws error if request already in progress with the same id.
 * @private
 */
lantern.subject.SubjectProviderXhr.prototype.sendRequest_ = function(
    id, uri, opt_callback) {

  if (this.currentRequests_.containsKey(id)) {
    throw Error('Duplicate request issued for ' + id);
  }
  this.currentRequests_.set(id, opt_callback);
  this.xhr_.send(id, uri, 'GET', undefined /* POST data */,
                 undefined /* no headers */,
                 lantern.subject.SubjectProviderXhr.DEFAULT_XHR_PRIORITY_);
};


/**
 * Callback for AJAX success.
 * @param {Event} e Event passed back from XhrManager.
 * @private
 */
lantern.subject.SubjectProviderXhr.prototype.onRemoteSuccess_ = function(e) {
  var id = e.id;
  var xhrIo = e.xhrIo;
  var callback = this.currentRequests_.get(id);
  this.currentRequests_.remove(id);

  // NOTE(vchen,ssaviano): getResponseJson is not used because it uses
  // goog.json.parse, which is a safer way to parse JSON but slower. As long
  // as the source is trusted, below is ok.
  var response = goog.json.unsafeParse(xhrIo.getResponseText());
  var result;
  var errmsg;

  if (!response.length || (2 != response.length)) {
    errmsg = 'Unexpected response';
  } else {
    result = response[1];
  }
  if (callback) {
    goog.Timer.callOnce(goog.bind(callback, this, id, result, errmsg), 10);
  }
  e.dispose();
};


/**
 * Callback for AJAX error.
 * @param {Event} e Event passed back from XhrManager.
 * @private
 */
lantern.subject.SubjectProviderXhr.prototype.onRemoteError_ = function(e) {
  var id = e.id;
  var xhrIo = e.xhrIo;
  var callback = this.currentRequests_.get(id);
  var msg = '';
  this.currentRequests_.remove(id);
  switch (e.type) {
    case goog.net.EventType.ERROR:
      msg = 'Xhr Error';
      break;
    case goog.net.EventType.ABORT:
      msg = 'Abort';
      break;
    case goog.net.EventType.TIMEOUT:
      msg = 'Timeout';
      break;
  }
  msg = ['Error(', msg, ') ', xhrIo.getLastError(), '(',
         xhrIo.getLastUri(), ')'];
  if (callback) {
    goog.Timer.callOnce(goog.bind(callback, this, id, undefined, msg.join('')),
                        10);
  }
  e.dispose();
};


goog.exportSymbol('lantern.subject.SubjectProviderXhr',
                  lantern.subject.SubjectProviderXhr);
