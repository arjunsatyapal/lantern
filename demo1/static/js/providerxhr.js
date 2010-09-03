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
 * @fileoverview This module contains DataProviderXhr that's a helper class
 * for issuing XHR requests.
 *
 * <p>Use {@code sendRequest()} to issue a request. Provide an optional
 * callback to handle the response. The signature of the callback is:
 *
 *   callback(id, response, opt_errMsg)
 *
 * The {@code response} is auto decoded using JSON parse. If that fails,
 * {@code response} is the original text.
 *
 * <p>Call {@code dispose()} to release resources.
 */

goog.provide('lantern.DataProviderXhr');

goog.require('goog.events.EventHandler');
goog.require('goog.json');
goog.require('goog.net.XhrIo');
goog.require('goog.net.XhrManager');
goog.require('goog.Uri');


/**
 * The DataProviderXhr is a re-usable Xhr helper.  It has a sendRequest()
 * with a callback. The callback has the signature:
 *
 *   callback(id, result, opt_errorMsg)
 *
 * @constructor
 * @extends {goog.Disposable}
 */
lantern.DataProviderXhr = function() {
  goog.Disposable.call(this);

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
      10000     /* opt_timeoutInterval ms */
      );

  /**
   * Map that maps request IDs to caller-supplied callbacks. It also represents
   * in-flight requests to avoid duplicates.
   *
   * @type {goog.structs.Map}
   * @private
   */
  this.currentRequests_ = new goog.structs.Map();

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
goog.inherits(lantern.DataProviderXhr, goog.Disposable);


/**
 * Default priority for XhrManager requests.
 * @type {number}
 * @private
 */
lantern.DataProviderXhr.DEFAULT_XHR_PRIORITY_ = 100;


/**
 * @override
 */
lantern.DataProviderXhr.prototype.disposeInternal = function() {
  lantern.DataProviderXhr.superClass_.disposeInternal.call(this);

  this.xhr_.dispose();
  this.eh_.dispose();

  this.xhr_ = null;
  this.eh_ = null;
  this.currentRequests_ = null;
};


/**
 * Issue XHR/Json request. Provide an optional callback to get the response.
 *
 * @param {string} id The request id. If a request is already in progress,
 *     an error is thrown.
 * @param {string|goog.Uri} uri The request URI.
 * @param {Function} opt_callback Callback function when the request is
 *     complete.  The callback has the signature:
 *      callback(id, result, opt_errorMsg)
 *     where opt_errorMsg is not passed in if there were no errors.
 * @param {string} opt_method optional method. Default is 'GET'
 * @param {string} opt_content optional content for 'POST'
 * @throws error if request already in progress with the same id.
 */
lantern.DataProviderXhr.prototype.sendRequest = function(
    id, uri, opt_callback, opt_method, opt_content) {

  if (this.currentRequests_.containsKey(id)) {
    // Because we uniquely map a callback to a request ID, we cannot handle
    // duplicate IDs.
    throw Error('Duplicate request issued for ' + id);
  }
  this.currentRequests_.set(id, opt_callback);
  this.xhr_.send(
      id,
      uri,
      opt_method ? opt_method : 'GET',
      opt_content,
      undefined /* no headers */,
      lantern.DataProviderXhr.DEFAULT_XHR_PRIORITY_);
};


/**
 * Internal Callback for AJAX success.
 * @param {Event} e Event passed back from XhrManager.
 * @private
 */
lantern.DataProviderXhr.prototype.onRemoteSuccess_ = function(e) {
  var id = e.id;
  var xhrIo = e.xhrIo;
  var callback = this.currentRequests_.get(id);
  this.currentRequests_.remove(id);

  var result;
  // Always tries to convert from JSON. If it fails, returns raw text.
  try {
    result = xhrIo.getResponseJson();
  } catch (e) {
    result = xhrIo.getResponseText();
  }
  var errmsg;
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
lantern.DataProviderXhr.prototype.onRemoteError_ = function(e) {
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
