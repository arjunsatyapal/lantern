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
 * @fileoverview Widget to show and manipulate the subscription status
 *     for the current page.
 */

goog.provide('lantern.subscription.PageStatus');

goog.require('goog.Disposable');
goog.require('goog.dom');
goog.require('goog.json');
goog.require('goog.events.EventHandler');

goog.require('lantern.DataProviderXhr');

/**
 * Make the placeholder <a> tag into subscription status control
 */
lantern.subscription.PageStatus = function(id, trunk_id) {
  goog.Disposable.call(this);

  this.trunk_id = trunk_id;
  this.eh_ = new goog.events.EventHandler(this);
  this.aElt_ = document.getElementById(id).firstChild;
  this.xhr_ = new lantern.DataProviderXhr();
  goog.dom.removeChildren(this.aElt_);
  goog.dom.setTextContent(this.aElt_, "Subscribed?");
  this.asyncGetStatus();
};
goog.inherits(lantern.subscription.PageStatus, goog.Disposable);


lantern.subscription.PageStatus.prototype.disposeInternal = function() {
  lantern.subscription.PageStatus.superClass_.disposeInternal.call(this);

  this.eh_.dispose();
  this.eh_ = null;
  this.aElt_ = null;
  this.xhr_.dispose();
  this.xhr_ = null;
};


lantern.subscription.PageStatus.prototype.asyncGetStatus = function() {
  var callback = goog.bind(this.processStatus, this);
  var uri = this.getXhrUri_('get');
  var data = { 'trunk_id': this.trunk_id };
  var contents = ["data=",
                  goog.json.serialize(data),
                  '&amp;xsrf_token=',
                  xsrfToken].join('');
  this.xhr_.sendRequest(undefined /* auto id */, uri, callback, 'POST', contents);
};


lantern.subscription.PageStatus.prototype.processStatus = function(
    id, result, opt_errMsg) {
  if (result && 'status' in result) {
    goog.dom.setTextContent(this.aElt_, result['status']);
  }
};


/**
 * Default base URL for XHR requests.
 * @type {string}
 * @private
 */
lantern.subscription.PageStatus.DEFAULT_XHR_URI_ = '/subscription/';


/**
 * Returns the URI to use for XHR.
 * @param {string?} action The action, 'get' or 'update'.
 * @return {goog.Uri}
 */
lantern.subscription.PageStatus.prototype.getXhrUri_ = function(action) {
  var uri = new goog.Uri(lantern.subscription.PageStatus.DEFAULT_XHR_URI_
                         + (action ? action : ''));
  return uri;
};
