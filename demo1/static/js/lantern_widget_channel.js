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
 * @fileoverview Library for communication back with Lantern Doc.
 *
 * To be included by Widget App that is referenced in the IFRAME.
 *
 * NOTE: Implementation depends on the Closure JavaScript Library.
 * http://code.google.com/closure/library.
 *
 * Typical usage:
 * <script type="text/javascript">
 *   goog.require('goog.Disposable');
 * </script>
 * <script src="/js/lantern_widget_channel.js"></script>
 *
 * To support browsers with no native transport, the Host and Widget apps must
 * be able to serve the files, "blank.html" and "relay.html", found at:
 * http://closure-library.googlecode.com/svn/trunk/closure/goog/demos/xpc/.
 *
 * Widget App must instantiate LanternWidgetChannel object.
 *
 * For accessing the channel for obtaining and updating score/data,
 * the Widget App JS should use the following methods on the instantiated
 * object (e.g., widgetChannel is the instantiated object):
 *
 *   widgetChannel.updateProgress
 *   widgetChannel.updateSession
 *   widgetChannel.updateLayout
 *
 * Additionally, the caller registers a callbackto receive session information
 * from the host Lantern Doc.
 *
 * Please see function definition below for description of each method.
 * These methods must be called after initializing the channel.
 *
 * This class registers the following XPC "services" that may be called by
 * the Host app:
 *
 *   init_session: Notifies the Widget that the Host has connected and is
 *       ready to receive calls. Because of variability in connection set up,
 *       this may be called after the Widget has already sent its own
 *       'init_session' request to the Host.
 *   send_session: Called by Host to send session information to the Widget.
 *       The payload is a JSON-encoded object of the form:
 *       {'session_id': session_id,
 *        'progress': progress,
 *        'score': score,
 *        'user_data': user_data}
 *       If the channel is constructed with a callback, that callback will
 *       be called with the session info.
 *
 * NOTE: The constructor also saves a session cookie to preserve the XPC channel
 * information.
 */
goog.provide('lantern.widget.LanternWidgetChannel');

goog.require('goog.Disposable');
goog.require('goog.dom');
goog.require('goog.json');
goog.require('goog.net.cookies');
goog.require('goog.net.xpc.CrossPageChannel');
goog.require('goog.Uri');


/**
 * Constructor for widget channel.
 *
 * @param {Function?} opt_onInitialize Optional callback to call when the
 *     the Host App calls 'send_session', which means it's ready to receive
 *     updates. The callback receives a sessionInfo object of the form:
 *     {'session_id': session_id,  // may be treated a user id
 *      'progress': progress,      // Last progress sent to host
 *      'score': score,            // Last score sent to host
 *      'user_data': user_data     // user data sent to host.
 *     }
 *
 * @constructor
 */
lantern.widget.LanternWidgetChannel = function(opt_onSendSession) {
  goog.Disposable.call(this);

  /**
   * Optional callback for responding to send_session
   * @type Function
   * @private
   */
  this.onSendSession_ = opt_onSendSession;

  /**
   * XPC configuration retrieved from the current URL or cookie.
   * If null, scores will not be propagated to the Host App.
   */
  this.cfg_ = null;

  // Extract XPC parameter from the URL or cookie
  var xpcParam = new goog.Uri(window.location.href).getParameterValue('xpc');
  if (xpcParam) {
    this.cfg_ = goog.json.parse(xpcParam);
    goog.net.cookies.set(
        lantern.widget.LanternWidgetChannel.COOKIE_NAME_XPC_, xpcParam);
  } else {
    xpcParam = goog.net.cookies.get(
        lantern.widget.LanternWidgetChannel.COOKIE_NAME_XPC_);
    if (xpcParam) {
      this.cfg_ = goog.json.parse(xpcParam);
    }
  }

  this.channel_ = new goog.net.xpc.CrossPageChannel(this.cfg_);
  this.initializeChannel_(goog.bind(this.onConnect_, this));

  /**
   * Session Id sent by host. This can be treated as an opaque user ID.
   * @type string
   * @private
   */
  this.sessionId_ = null;
};
goog.inherits(lantern.widget.LanternWidgetChannel, goog.Disposable);


/**
 * Cookie name to preserve XPC channel info.
 * @private
 */
lantern.widget.LanternWidgetChannel.COOKIE_NAME_XPC_ =
    'lantern_widget_channel_cfg';


/**
 * @override
 */
lantern.widget.LanternWidgetChannel.prototype.disposeInternal = function() {
  this.channel_.dispose();
  this.channel_ = null;

  lantern.widget.LanternWidgetChannel.superClass_.disposeInternal.call(this);
};


/**
 * Returns current session ID.
 */
lantern.widget.LanternWidgetChannel.prototype.getSessionId = function() {
  return this.sessionId_;
};


/**
 * Internal handler for send_session.
 *
 * @param {string} payload Payload sent from Host app. It is expected to be
 *    a JSON-encoded dict of the form:
 *     {'session_id': session_id,  // may be treated a user id
 *      'progress': progress,      // Last progress sent to host
 *      'score': score,            // Last score sent to host
 *      'user_data': user_data     // user data sent to host.
 *     }
 * @private
 */
lantern.widget.LanternWidgetChannel.prototype.sendSession_ = function(
    payload) {
  var sessionInfo = goog.json.parse(payload);
  if (sessionInfo) {
    this.sessionId_ = sessionInfo['session_id'];
  }
  if (this.onSendSession_) {
    this.onSendSession_(sessionInfo);
  }
};


/**
 * Function to initialize the lanternChannel object.
 */
lantern.widget.LanternWidgetChannel.prototype.initializeChannel_ = function(
    callback) {

  this.channel_.registerService('init_session',
      goog.bind(this.onInitSession_, this));
  this.channel_.registerService('send_session',
      goog.bind(this.sendSession_, this));

  this.channel_.connect(callback);
};


/**
 * Wrapper for exposing XPC channel's send method.
 *
 * @param {string} service Name of the service.
 * @param {string} opt_payload Optional payload to be passed to the service.
 */
lantern.widget.LanternWidgetChannel.prototype.send = function(
    service, opt_payload) {
  this.channel_.send(service, opt_payload);
};


/**
 * Sends init-session message to Host app.
 *
 * @param {boolean} force If true, forces re-initialization.
 */
lantern.widget.LanternWidgetChannel.prototype.sendInitSession = function(
    force) {
  this.send('init_session', force ? 'force' : '');
};


/**
 * Called when connection is established.
 */
lantern.widget.LanternWidgetChannel.prototype.onConnect_ = function() {
  this.sendInitSession(true);
};


/**
 * Called when "ini_session" message is received from the host.
 */
lantern.widget.LanternWidgetChannel.prototype.onInitSession_ = function(
    payload) {
  // This essentially completes a handshake with HOST to indicate the Widget
  // is ready. It occurs when the host is "late" in connecting,
  this.sendInitSession(false);
};


/**
 * Updates progress, sending it to the host.
 *
 * @param {Object} progress dict of the form:
 *     {'progress': progress,
 *      'score: score,
 *     }
 */
lantern.widget.LanternWidgetChannel.prototype.updateProgress = function(
    progress) {
  var payload = goog.json.serialize(progress);
  this.send('update_progress', payload);
};


/**
 * Updates session info.
 * Wrapper around the native send messages via channels.
 *
 * @param {number} progress Progress, from 0 to 100.
 * @param {number} score Score, from 0 to 100.
 * @param {string} user_data An opaque "blob" to send to the host for
 *     persisting. Typically, it's been JSON encoded.
 */
lantern.widget.LanternWidgetChannel.prototype.updateSession = function(
    progress, score, user_data) {
  var sessionInfo = {
    'session_id': this.sessionId_,
    'progress': progress,
    'score': score,
    'user_data': user_data
  }
  var payload = goog.json.serialize(sessionInfo);
  this.send('update_session', payload);
};


/**
 * Updates layout info.
 * Wrapper around the native send messages via channels.
 */
lantern.widget.LanternWidgetChannel.prototype.updateLayout = function() {
  var height = goog.dom.getDocumentHeight();
  var sz = goog.dom.getViewportSize();
  if (sz.height < height) {
    var layout = {
      'height': height
    }
    var payload = goog.json.serialize(layout);
    this.send('update_layout', layout);
  }
};
