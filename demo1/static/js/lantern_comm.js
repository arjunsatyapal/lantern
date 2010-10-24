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
 * @fileoverview Library for communicating between Lantern docs and widgets.
 *
 * Lantern docs host embedded widgets. This is the host-side library that
 * helps set up Widget IFrames and communication channels.
 *
 * Each IFrame which needs to communicate with doc, must be registered
 * using registerChannel() call.
 */

goog.provide('lantern.comm.LanternChannelFactory');
goog.provide('lantern.comm.LanternChannel');

goog.require('goog.Disposable');
goog.require('goog.dom');
goog.require('goog.dom.classes');
goog.require('goog.events');
goog.require('goog.events.EventHandler');
goog.require('goog.json');
goog.require('goog.net.xpc.CrossPageChannel');
goog.require('goog.structs');
goog.require('goog.style');
goog.require('goog.ui.Dialog');
goog.require('goog.Uri');

goog.require('lantern.DataProviderXhr');
goog.require('lantern.comm.LanternHostChannel');


/**
 * Constructor for Lantern Channel.
 *
 * @param {string} thirdPartyBaseUri Base uri for the thirdparty.
 * @param {string} iframeUri Complete uri to be embedded in an iframe.
 * @param {string} widgetId Id of the widget to be embedded in the Iframe.
 * @param {string} widgetIndex Index of the widget on the page.
 *    widgetId + widgetIndex is the id of the iframe container.
 * @param {string} doc_id Document Id.
 * @param {string} trunk_id Trunk Id for lantern doc.
 * @param {string} height Iframe's height.
 * @param {string} width Iframe's width.
 * @param {boolean} absolute If true absolute doc_id is used while fetching
 *   document. This is passed based on if absolute parameter was set while
 *   loading the document.
 * @constructor
 * @extends {goog.Disposable}
 *
 * NOTE(mukundjha): Using relative URI for communication seems to be working
 * although this should be tested more thoroughly.
 */
lantern.comm.LanternChannel = function(
    thirdPartyBaseUri, iframeUri, widgetId, widgetIndex, doc_id, trunk_id,
    height, width, absolute) {
  goog.Disposable.call(this);

  var ownUri = '/';
  var iframeContainerId = widgetId + widgetIndex;
  this.widgetId_ = widgetId;
  this.doc_id_ = doc_id;
  this.trunk_id_ = trunk_id;
  this.absolute_ = absolute;
  this.height_ = height;
  this.width_ = width;

  /**
   * Host-side channel for communicating with Widget app.
   * @type lantern.comm.LanternHostChannel
   * @private
   */
  this.hostChannel_ = new lantern.comm.LanternHostChannel(
      thirdPartyBaseUri, iframeUri, iframeContainerId,
      goog.bind(this.setIframeAttrs_, this),
      goog.bind(this.onConnect_, this));

  /**
   * Manger for XHR requests.
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

  // Bind host channel callbacks.
  this.hostChannel_.setOnInitSession(
      goog.bind(this.fetchSessionInfo_, this));
  this.hostChannel_.setOnUpdateProgress(
      goog.bind(this.updateProgress_, this));
  this.hostChannel_.setOnUpdateSession(
      goog.bind(this.updateSession_, this));
  this.hostChannel_.setOnUpdateLayout(
      goog.bind(this.updateLayout_, this));
};
goog.inherits(lantern.comm.LanternChannel, goog.Disposable);


/**
 * Helper to send a request via XHR that auto-increments the request ID.
 * @private
 */
lantern.comm.LanternChannel.prototype.sendRequest_ = function(
    uri, callback, opt_method, opt_content) {
  this.xhr_.sendRequest(
      undefined /* autogen ID */, uri, callback, opt_method, opt_content);
};


/**
 * Sets attributes for Iframe before loading.
 * TODO(mukundjha): Replace 'widgetFrame' with some parameter to be passed.
 *
 * @param {IFrameElement} iFrameElm Iframe element.
 * @private
 */
lantern.comm.LanternChannel.prototype.setIframeAttrs_ = function(iFrameElm){
  goog.style.setSize(iFrameElm, this.width_, this.height_);
  goog.dom.classes.add(iFrameElm, 'widgetFrame');
};


/**
 * Called when the connection has been established with the widget.
 *
 * @private
 */
lantern.comm.LanternChannel.prototype.onConnect_ = function(){
  // Nothing to do for now. Waiting for Widget to send init_session message.
};


/**
 * Fetches the session info and calls sendSessionToWidget_ to send it to the
 * widget.
 * Registered with the hostChannel_.
 * @param {string} iframeContainerId ID of the widget container.
 */
lantern.comm.LanternChannel.prototype.fetchSessionInfo_ = function(
    iframeContainerId) {
  var uri = '/getSession?widget_id=' + this.widgetId_;
  this.sendRequest_(uri, goog.bind(this.sendSessionToWidget_, this));
};


/**
 * Sends associated session information to the widget.
 * The function is triggered upon completion of AJAX request for session info.
 * @private
 */
lantern.comm.LanternChannel.prototype.sendSessionToWidget_ = function(
    id, result, opt_errorMsg) {
  var sessionInfo = result;
  // The session_info is a dict of the form:
  //  {'session_id': session_id,
  //   'progress': progress,
  //   'score': score,
  //   'user_data': user_data}
  this.hostChannel_.sendSessionInfo(sessionInfo);
};


/**
 * Updates the progress score for widget. Registered with the hostChannel_.
 *
 * @param {string} iframeContainerId ID of the widget container.
 * @param {string} progress Progress/Score of the form:
 *    {'progress': progress,
 *     'score': score}
 */
lantern.comm.LanternChannel.prototype.updateProgress_ = function(
    iframeContainerId, progress) {
  //alert('I am loop1');
  if ( lantern.comm.LanternChannelFactory.completed_
       && !lantern.comm.LanternChannelFactory.warnedOnce_) {
    //alert('I am loop 2');
    lantern.comm.LanternChannelFactory.warnedOnce_ = true;
    var dialog = new goog.ui.Dialog(null, true);
    var content = '<b>'
        + 'Attempting this will reset the score and '
        + 'progress for this module.'
        + '<ul>'
        + '<li>Click \"Keep scores\" to take the quiz again <em>without</em> '
        + 'affecting this module\'s score.'
        + '<li>Click \"Sync quiz scores\" to have the quiz score be reflected '
        + 'in this module.'
        + '</ul></b>';
    dialog.setContent(content);
    var buttonSet = new goog.ui.Dialog.ButtonSet();
    buttonSet.set('keep_score_button', 'Keep scores');
    buttonSet.set('reset_score_button', 'Sync quiz scores');
    dialog.setButtonSet(buttonSet);
    this.eh_.listenOnce(dialog, goog.ui.Dialog.EventType.SELECT,
                        goog.bind(this.handleResetOrKeep_, this));
   dialog.setVisible(true);
  }
  if (lantern.comm.LanternChannelFactory.completed_ ||
      lantern.comm.LanternChannelFactory.ignoreUpdateRequest_) {
    //alert('I am loop33');
    return;
  }
  var uri = new goog.Uri('/updateScore');
  uri.setParameterValue('widget_id', this.widgetId_);
  uri.setParameterValue('doc_id', this.doc_id_);
  uri.setParameterValue('trunk_id', this.trunk_id_);
  uri.setParameterValue('score', progress.score);
  uri.setParameterValue('progress', progress.progress);
  uri.setParameterValue('absolute', this.absolute_);

  this.sendRequest_(uri, goog.bind(this.processScore_, this));
};


/**
 * Handle Dialog response to keep or reset scores.
 * @private
 */
lantern.comm.LanternChannel.prototype.handleResetOrKeep_ = function(e) {
  if (e.key == 'reset_score_button'){
    //alert('i have chosen reset');
    lantern.comm.LanternChannelFactory.ignoreUpdateRequest_ = false;
    lantern.comm.LanternChannelFactory.completed_ = false;
  } else if (e.key == 'keep_score_button'){
    //alert('i have chosen to keep scores');
    lantern.comm.LanternChannelFactory.ignoreUpdateRequest_ = true;
    lantern.comm.LanternChannelFactory.completed_ = false;
  }
};


/**
 * Updates the accumulated progress score for the document.
 * This is an XHR callback to set the progress bar.
 *
 * @param {number} id Request ID associated with this response.
 * @param {object} response JSON decoded response (if possible) or the original
 *     response.
 * @param {string?} opt_errorMsg Optional XHR error message.
 * @private
 */
lantern.comm.LanternChannel.prototype.processScore_ = function(
    id, result, opt_errorMsg) {
  //alert('updating score : ' + obj);
  var docProgressBar = goog.dom.getElement('docProgressBar');
  var progressHtmlArray = [
      'http://chart.apis.google.com/chart?chs=150x25&chd=t:',
      result.doc_score,
      '|100&cht=bhs&chds=0,100&chco=4D89F9,C6D9FD&chxt=y,r&chxl=0:||1:||',
      '&chm=N,000000,0,-1,11'];

  docProgressBar.src = progressHtmlArray.join('');
};


/**
 * Updates session info for widget. Registered with hostChannel_.
 *
 * @param {string} iframeContainerId ID of the Widget container.
 * @param {Object} sessionInfo Session info to write back to the server.
 */
lantern.comm.LanternChannel.prototype.updateSession_ = function(
    iframeContainerId, sessionInfo) {
  var uri = new goog.Uri('/updateWidgetSession');
  var qd = new goog.Uri.QueryData();
  qd.set('xsrf_token', xsrfToken /* global var */);
  qd.set('widget_id', this.widgetId_);
  qd.set('doc_id', this.doc_id_);
  qd.set('trunk_id', this.trunk_id_);
  qd.set('absolute', this.absolute_);

  qd.set('user_data', sessionInfo['user_data']);
  if (!lantern.comm.LanternChannelFactory.completed_ &&
      !lantern.comm.LanternChannelFactory.ignoreUpdateRequest_) {
    qd.set('score', sessionInfo['score']);
    qd.set('progress', sessionInfo['progress']);
  }
  this.sendRequest_(
      uri, goog.bind(this.processScore_, this), 'POST', qd.toString());
};


/**
 * Request to update layout. The current implementation only adjusts
 * the viewport height to fit the widget.
 *
 * @param {string} iframeContainerId ID of the Widget container.
 * @param {Object} layout A dict of the form:
 *     {'width': width,
 *      'height': height}
 */
lantern.comm.LanternChannel.prototype.updateLayout_ = function(
    iframeContainerId, layout) {
  if (this.hostChannel_) {
    var iframe = this.hostChannel_.getWidgetIframe();
    if (iframe && layout['height']) {
      this.height_ = layout['height'] + 'px';
      goog.style.setSize(iframe, this.width_, this.height_);
    }
  }
};


/**
 * Initializes LanternChannel object by registering required methods.
 * This represents the API that the Widget can use to call the Host app.
 */
lantern.comm.LanternChannel.prototype.initializeChannel = function(){
  this.hostChannel_.initialize();
};


/**
 * @override
 */
lantern.comm.LanternChannel.prototype.disposeInternal = function() {
  this.channel_.dispose();
  this.xhr_.dispose();
  this.eh_.dispose();

  lantern.comm.LanternChannel.superClass_.disposeInternal.call(this);
};


/**
 * Factory class for creating LanternChannel objects.
 * @constructor
 */
lantern.comm.LanternChannelFactory = function() {
  // Nothing
};


/**
 * Factory class variable to maintain a map of channels (keyed on IFrame's
 * container id).
 * Each element is a separate channel for a different IFrame.
 * @type Map.<Object>
 * @private
 */
lantern.comm.LanternChannelFactory.channelMap_ = {};


/**
 * Global variable to maintain state controlling if the update has to be made.
 * @type Boolean
 * @private
 */
lantern.comm.LanternChannelFactory.ignoreUpdateRequest_ = false;


/**
 * Global variable indicating if progress is 100% for the current doc.
 * @type Boolean
 * @private
 */
lantern.comm.LanternChannelFactory.completed_ = false;


/**
 * Global variable set true if warning has already been issued
 * @type Boolean
 * @private
 */
lantern.comm.LanternChannelFactory.warnedOnce_ = false;


/**
 * Factory method for creating/registering a new channel.
 * To be called in view.html. Must call initialize() to initialize all
 * registered channels.
 *
 * @param {string} thirdPartyBaseUri Base uri for the thirdparty.
 * @param {string} iframeUri Complete uri to be embedded in an iframe.
 * @param {string} widgetId Id of the widget to be embedded in the Iframe.
 * @param {string} widgetIndex Index of the widget on the page.
 *    widgetId + widgetIndex is the id of the iframe container.
 * @param {string} doc_id Document Id.
 * @param {string} trunk_id Trunk Id for lantern doc.
 * @param {string} height Iframe's height.
 * @param {string} width Iframe's width.
 * @param {boolean} absolute If true absolute doc_id is used while fetching
 *   document. This is passed based on if absolute parameter was set while
 *   loading the document.
 * @param {boolean} completed If true implies module is already completed.
 */
lantern.comm.LanternChannelFactory.registerChannel = function(
    thirdPartyBaseUri, iframeUri, widgetId, widgetIndex, doc_id,
    trunk_id, height, width, absolute, completed) {

  var iframeContainerId = widgetId + widgetIndex;

  lantern.comm.LanternChannelFactory.channelMap_[iframeContainerId] =
      new lantern.comm.LanternChannel(
          thirdPartyBaseUri, iframeUri, widgetId, widgetIndex,
          doc_id, trunk_id, height, width, absolute);
};


/**
 * Initializes all registered channels. Place a call to this at the bottom
 * of the HTML page.
 */
lantern.comm.LanternChannelFactory.initialize = function(isCompleted) {
   lantern.comm.LanternChannelFactory.completed_ = isCompleted;

   goog.structs.forEach(
       lantern.comm.LanternChannelFactory.channelMap_,
       function(channel, key, collection) {
         channel.initializeChannel();
       });

   // Make sure channels are released.
   goog.events.listen(window, 'unload', function(e) {
       lantern.comm.LanternChannelFactory.dispose();
     });
};


/**
 * Clean up channels. To be called from a window-unload handler.
 */
lantern.comm.LanternChannelFactory.dispose = function() {
  goog.structs.forEach(
      lantern.comm.LanternChannelFactory.channelMap_,
      function(channel, key, collection) {
        channel.dispose();
      });
  goog.structs.clear(lantern.comm.LanternChannelFactory.channelMap_);
};


// On load function to be written in the html after getting iframe information.

goog.exportSymbol(
    'lantern.comm.LanternChannelFactory.registerChannel',
    lantern.comm.LanternChannelFactory.registerChannel);
goog.exportSymbol(
    'lantern.comm.LanternChannelFactory.initialize',
    lantern.comm.LanternChannelFactory.initialize);
