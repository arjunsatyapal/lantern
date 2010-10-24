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
 * @fileoverview Implementation for Host-side of the Lantern Widget API.
 *
 * The LanternHostChannel wraps Host-side Lantern Widget API. To use it,
 * construct and attach callbacks to handle widget requests.
 *
 * This registers the following XPC "services" that may be called by the Widget
 * app:
 *   init_session: Notifies Host that the widget is ready. Payload may be:
 *       'force': Force initialize the session, even if it was done already.
 *       '': Only initialize the session if it has not been initialized.
 *   update_progress: Updates Host with widget progress/score. Payload is
 *       JSON-encoded dict of the form:
 *         {'progress': progress,
 *          'score': score}
 *       where each is expected to be a number from 0 to 100.
 *       Progress indicates how far of the material the user has completed.
 *       Score indicates the user's score on that material.
 *       NOTE: Lantern currently only uses progress.
 *   update_session: Updates Host with widget session info. Payload is
 *       JSON-encoded dict of the form:
 *         {'session_id': session_id,
 *          'progress': progress,
 *          'score': score,
 *          'user_data': user_data}
 *       where user_data is an opaque string stored on behalf of the widget.
 *       Typically, it is itself a JSON-encoded string.
 *   update_layout: Updates Host with widget's desired layout. Payload is
 *       JSON-encoded dict of the form:
 *         {'width': width,
 *          'height': height}
 *       where each is an integer representing pixels (px).
 *
 * Host calls the following service on the Widget:
 *   send_session: Sends session info that was saved on behalf of the widget
 *       via update_session.
 */

goog.provide('lantern.comm.LanternHostChannel');

goog.require('goog.Disposable');
goog.require('goog.dom');
goog.require('goog.events');
goog.require('goog.events.EventHandler');
goog.require('goog.json');
goog.require('goog.net.xpc.CrossPageChannel');
goog.require('goog.Uri');

/**
 * Constructor for a Lantern Host-side Channel.
 *
 * It sets up the Cross Page Channel (XPC) using the specified IFrame
 * container. The third-party widget must serve the following files:
 *
 *   widgetBaseUri + 'blank.html'
 *   widgetBaseUri + 'relay.html'
 *
 * @param {string} widgetBaseUri The base URI of the widget app. This is used
 *     to locate blank.html and relay.html on the third-party site, needed
 *     by some browsers to set up a polling transport.
 * @param {string} iframeUri Complete uri to be embedded in an iframe.
 * @param {string} iframeContainerId The element ID of the iframe that is
 *     to contain the widget. This is used to set up the XPC channel.
 * @param {Function?} opt_configureIframeCb Optional callback to call configure
 *     the IFrame. The IFrame element is passed to the callback.
 * @param {Function?} opt_onConnect Optional callback to call when the
 *     the XPC connection is established. The callback is passed the IFrame
 *     DOM element.
 *
 * @constructor
 * @extends {goog.Disposable}
 */
lantern.comm.LanternHostChannel = function(
    widgetBaseUri, iframeUri, iframeContainerId,
    opt_configureIframeCb, opt_onConnect) {
  goog.Disposable.call(this);

  var ownUri = '/';
  this.iframeContainerId_ = iframeContainerId;
  this.onConnect_ = opt_onConnect;
  this.cfg_ = {};

  this.cfg_[goog.net.xpc.CfgFields.PEER_URI] = iframeUri;

  // Configuration specific to the Iframe Polling transport. Required,
  // because the Iframe Polling transport may be required for some
  // browsers.

  this.cfg_[goog.net.xpc.CfgFields.PEER_POLL_URI] =
      widgetBaseUri + 'blank.html';
  this.cfg_[goog.net.xpc.CfgFields.LOCAL_POLL_URI] =
      ownUri + 'blank.html';

  // Configuration specific to the Iframe Relay transport. Required,
  // because the Iframe Relay transport may be required for some
  // browsers.

  this.cfg_[goog.net.xpc.CfgFields.PEER_RELAY_URI] =
      widgetBaseUri + 'relay.html';
  this.cfg_[goog.net.xpc.CfgFields.LOCAL_RELAY_URI] =
      ownUri + 'relay.html';

  this.channel_ = new goog.net.xpc.CrossPageChannel(this.cfg_);

  this.iframeElem_ = this.channel_.createPeerIframe(
      goog.dom.getElement(iframeContainerId), opt_configureIframeCb);

  // Callbacks to handle widget app notifications.
  this.onInitSession_ = null;
  this.onUpdateProgress_ = null;
  this.onUpdateSession_ = null;
  this.onUpdateLayout_ = null;

  // Whether session information have already been sent to Widget.
  this.isWidgetInitialized_ = false;
};
goog.inherits(lantern.comm.LanternHostChannel, goog.Disposable);


/**
 * @override
 */
lantern.comm.LanternHostChannel.prototype.disposeInternal = function() {
  this.channel_.dispose();

  this.onInitSession_ = null;
  this.onUpdateProgress_ = null;
  this.onUpdateSession_ = null;
  this.onUpdateLayout_ = null;

  this.channel_ = null;
  this.iframeElem_ = null

  lantern.comm.LanternHostChannel.superClass_.disposeInternal.call(this);
};


/**
 * Returns the IFRAME element that contains the widget app.
 */
lantern.comm.LanternHostChannel.prototype.getWidgetIframe = function() {
  return this.iframeElem_;
};


/**
 * Sets the handler for "init_session" request from the Widget App.
 * The signature of the callback is:
 *
 *   onInitSession(iframeContainerId);
 *
 * where iframeContainerId was passed into the constructor. The callback is
 * expected to (eventually) call sendSessionInfo() to send session info to
 * the widget app.
 *
 * @param {Function} onInitSession The callback for handling session
 *     initialization.
 */
lantern.comm.LanternHostChannel.prototype.setOnInitSession = function(
    onInitSession) {
  this.onInitSession_ = onInitSession;
};


/**
 * Sets the handler for "update_progress" notification from the Widget App.
 * The signature of the callback is:
 *
 *   onUpdateProgress(iframeContainerId, progress)
 *
 * where iframeContainerId was passed into the constructor and progress is
 * a dict of the form:
 *    {'progress': progress,
 *     'score': score
 *    }
 *
 * Progress and score may be different, where progress means percentage of
 * the way through the material and score measures how well the user has done.
 *
 * @param {Function} onUpdateProgress The callback for handling progress
 *     notification.
 */
lantern.comm.LanternHostChannel.prototype.setOnUpdateProgress = function(
    onUpdateProgress) {
  this.onUpdateProgress_ = onUpdateProgress;
};


/**
 * Sets the handler for "update_session" notification from the Widget App.
 * The signature of the callback is:
 *
 *   onUpdateSession(iframeContainerId, sessionInfo)
 *
 * where iframeContainerId was pass into the constructor and sessionInfo is a
 * map of the form:
 *
 * { 'session_id': session_id,
 *   'progress': progress,
 *   'score': score,
 *   'user_data': user_data
 * }
 *
 * @param {Function} onUpdateSession The callback for handling session-data
 *     notification.
 */
lantern.comm.LanternHostChannel.prototype.setOnUpdateSession = function(
    onUpdateSession) {
  this.onUpdateSession_ = onUpdateSession;
};


/**
 * Sets the handler for "update_layout" notification from the Widget App.
 * The signature of the callback is:
 *
 *   onUpdateLayout(iframeContainerId, layoutInfo)
 *
 * where iframeContainerId was passed into the constructor and layoutInfo is a
 * map of the form:
 *
 * { 'width': width,
 *   'height': height
 * }
 *
 * These are the only two defined currently and the callback is free to ignore
 * them.
 *
 * @param {Function} onUpdateLayout The callback for handling layout
 *     notification.
 */
lantern.comm.LanternHostChannel.prototype.setOnUpdateLayout = function(
    onUpdateLayout) {
  this.onUpdateLayout_ = onUpdateLayout;
};


/**
 * Send session info to the widget app.
 *
 * @param {Object} sessionInfo This is expected to be a dict of the form:
 *     {'session_id': session_id,
 *      'progress': progress,
 *      'score': score,
 *      'user_data': user_data}
 *     It will be json encoded before passing it to the widget app.
 * @private
 */
lantern.comm.LanternHostChannel.prototype.sendSessionInfo = function(
    sessionInfo) {
  var sessionJson = goog.json.serialize(sessionInfo);
  this.channel_.send('send_session', sessionJson);
};


/**
 * Internal handler for onConnect. It sends init_session message to the
 * Widget.
 *
 * @private
 */
lantern.comm.LanternHostChannel.prototype.onConnectInternal_ = function() {
  this.channel_.send('init_session', '');
  if (this.onConnect_) {
    this.onConnect_();
  }
};


/**
 * Internal handler for init_session. This may be called multiple times when
 * performing start-up handshake, so it checks for whether it was already
 * initialized.
 *
 * @param {string} payload Payload sent from the widget app. Ignored.
 * @private
 */
lantern.comm.LanternHostChannel.prototype.initWidgetSession_ = function(
    payload) {
  if (payload != 'force' && this.isWidgetInitialized_) {
    return;
  }
  if (this.onInitSession_) {
    this.onInitSession_(this.iframeContainerId_);
  }
  this.isWidgetInitialized_ = true;
};


/**
 * Internal handler for update_progress.
 *
 * @param {string} payload Payload sent from the widget app. It is expected
 *     to be a JSON-encoded dict of the form:
 *       {'progress': progress,
 *        'score': score}
 *     where progress is a number from 0 to 100.
 * @private
 */
lantern.comm.LanternHostChannel.prototype.updateWidgetProgress_ = function(
    payload) {
  var obj = goog.json.parse(payload);
  if (obj && this.onUpdateProgress_) {
    this.onUpdateProgress_(this.iframeContainerId_, obj);
  }
};


/**
 * Internal handler for update_session.
 *
 * @param {string} payload Payload sent from the widget app. It is expected
 *     to be a JSON-encoded dict of the form:
 *       {'session_id': session_id,
 *        'progress': progress,
 *        'score': score,
 *        'user_data': user_data
 *        }
 *     where progress is a number from 0 to 100.
 * @private
 */
lantern.comm.LanternHostChannel.prototype.updateWidgetSession_ = function(
    payload) {
  var sessionInfo = goog.json.parse(payload);
  if (sessionInfo && this.onUpdateSession_) {
    this.onUpdateSession_(this.iframeContainerId_, sessionInfo);
  }
};


/**
 * Internal handler for update_layout.
 *
 * @param {string} payload Payload sent from the widget app. It is expected
 *     to be a JSON-encoded dict of the form:
 *       {'width': width,
 *        'height': height
 *        }
 * @private
 */
lantern.comm.LanternHostChannel.prototype.updateWidgetLayout_ = function(
    payload) {
  var layout = goog.json.parse(payload);
  if (layout && this.onUpdateLayout_) {
    this.onUpdateLayout_(this.iframeContainerId_, layout);
  }
};


/**
 * Initializes LanternHostChannel object by registering required methods.
 * This represents the API that the Widget can use to call the Host app.
 */
lantern.comm.LanternHostChannel.prototype.initialize = function(){
  this.channel_.registerService(
      'init_session',
      goog.bind(this.initWidgetSession_, this));

  this.channel_.registerService(
      'update_progress',
      goog.bind(this.updateWidgetProgress_, this));

  this.channel_.registerService(
      'update_session',
      goog.bind(this.updateWidgetSession_, this));

  this.channel_.registerService(
      'update_layout',
      goog.bind(this.updateWidgetLayout_, this));

  this.channel_.connect(
      goog.bind(this.onConnectInternal_, this));
};
