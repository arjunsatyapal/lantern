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
goog.require('goog.Uri');

goog.require('lantern.DataProviderXhr');
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
   * @type {latern.DataProviderXhr}
   * @private
   */
  this.xhr_ = new lantern.DataProviderXhr();
};
goog.inherits(lantern.subject.SubjectProviderXhr,
              lantern.subject.SubjectProvider);


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
  this.xhr_.sendRequest(id, uri, goog.bind(this.onDataReady_, this));
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
  var subjects;
  // Expect a 2-element array.
  if (!result.length || (2 != result.length)) {
    errmsg = 'Unexpected response';
  } else {
    subjects = result[1];
    this.mergeSubjects_(id, subjects);
    this.dispatchEvent(lantern.subject.SubjectProvider.EventType.DATA_READY);
  }
};


/**
 * @inheritDoc
 */
lantern.subject.SubjectProviderXhr.prototype.disposeInternal = function() {
  lantern.subject.SubjectProviderXhr.superClass_.disposeInternal.call(this);

  this.xhr_.dispose();
  this.xhr_ = null;
};


goog.exportSymbol('lantern.subject.SubjectProviderXhr',
                  lantern.subject.SubjectProviderXhr);
