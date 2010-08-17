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
 * @fileoverview Library for communicating with Lantern docs.
 * To be included in view.html for lantern.
 * Each IFrame which needs to communicate with doc, must be registered
 * using RegisterChannel call.
 */

goog.provide('lantern.comm.LanternChannelFactory');
goog.provide('lantern.comm.LanternChannel');

goog.require('goog.dom');
goog.require('goog.json');
goog.require('goog.net.XhrIo');
goog.require('goog.net.xpc.CrossPageChannel');
goog.require('goog.Uri');
goog.require('goog.style');
goog.require('goog.ui.Dialog');
/**
 * Constructor for Lantern Channel.
 * @param {string} thirdPartyBaseUri Base uri for the thirdparty.
 * @param {string} iframeUri Complete uri to be embedded in an iframe.
 * @param {string} iframeContainerId Id of the container of the Iframe.
 * @param {string} doc_id Document Id.
 * @param {string} trunk_id Trunk Id for lantern doc.
 * @param {string} height Iframe's height.
 * @param {string} width Iframe's width.
 * @param {boolean} absolute If true absolute doc_id is used while fetching
 *   document. This is passed based on if absolute parameter was set while
 *   loading the document.
 * @param {boolean} completed If true implies module is already completed.
 * @constructor
 * NOTE(mukundjha): Using relative URI for communication seems to be working
 * although this should be tested more thoroughly.
 */
lantern.comm.LanternChannel = function(
    thirdPartyBaseUri, iframeUri, iframeContainerId, doc_id, trunk_id,
    height, width, absolute, completed) {
  var ownUri = '/'
  this.iframeId_ = iframeContainerId;
  this.cfg_ = {};
  this.doc_id_ = doc_id;
  this.trunk_id_ = trunk_id;
  this.absolute_ = absolute;
  this.height_ = height;
  this.width_ = width;
  this.completed_ = completed;

  this.cfg_[goog.net.xpc.CfgFields.PEER_URI] = iframeUri;
  // Configuration specific to the Iframe Polling transport. Required,
  // because the Iframe Polling transport may be required for some
  // browsers.

  this.cfg_[goog.net.xpc.CfgFields.PEER_POLL_URI] = thirdPartyBaseUri +
    'blank.html';
  this.cfg_[goog.net.xpc.CfgFields.LOCAL_POLL_URI] = ownUri + 'blank.html';
  
  // Configuration specific to the Iframe Relay transport. Required,
  // because the Iframe Relay transport may be required for some
  // browsers.

   this.cfg_[goog.net.xpc.CfgFields.PEER_RELAY_URI] = thirdPartyBaseUri + 
     'relay.html';
   this.cfg_[goog.net.xpc.CfgFields.LOCAL_RELAY_URI] = ownUri + 'relay.html';
   this.channel_ = new goog.net.xpc.CrossPageChannel(this.cfg_);

   this.channel_.createPeerIframe(
       goog.dom.getElement(iframeContainerId),
       goog.bind(this.setIframeAttrs, this));
  
   this.xhr_ = new goog.net.XhrIo();
};


/**
 * Sets attributes for Iframe before loading.
 * @param {IFrameElement} iFrameElm Iframe element.
 */
lantern.comm.LanternChannel.prototype.setIframeAttrs = function(iFrameElm){
  goog.style.setSize(iFrameElm, this.width_, this.height_);
};


/**
 * Updates the accumulated progress score for the document.
 */
lantern.comm.LanternChannel.prototype.processScore = function() {
  var obj = this.xhr_.getResponseJson();
  //alert('updating score : ' + obj); 
  var docProgressContainer = goog.dom.getElement('docProgressContainer');
   progressHtmlArray = [
      '<b>Progress: </b>',
      '<img src="http://chart.apis.google.com/chart?chs=150x25&chd=t:',
      obj.doc_score,
      '|100&cht=bhs&chds=0,100&chco=4D89F9,C6D9FD&chxt=y,r&chxl=0:||1:||',
      '&chm=N,000000,0,-1,11"'];

  docProgressContainer.innerHTML = progressHtmlArray.join('');
};


/**
 * Updates the progress score for widget. This is registered as a service.
 * param {string} data Incomming payload.
 */
lantern.comm.LanternChannel.prototype.updateScore = function(data) {
  //alert('I am loop1');
  if ( lantern.comm.LanternChannelFactory.completed_ 
       && !lantern.comm.LanternChannelFactory.warnedOnce_) {
    //alert('I am loop 2');
    lantern.comm.LanternChannelFactory.warnedOnce_ = true;
    var dialog = new goog.ui.Dialog(null, true);
    var content = '<b> Attempting this will reset the score and ' +
                  'progress for this module.<br/>' + 'If you wish to keep the current scores ' +
                  ' please click \'Keep scores\',<br/>you will still be able to attempt but it will' +
                  ' not reflect on this module.<br/> Or click Reset scores to reset it </b>';
    dialog.setContent(content);
    var buttonSet = new goog.ui.Dialog.ButtonSet();
    buttonSet.set('keep_score_button', 'Keep scores');
    buttonSet.set('reset_score_button', 'Reset scores');
    dialog.setButtonSet(buttonSet);
    goog.events.listen(dialog, goog.ui.Dialog.EventType.SELECT, function(e) {
      if( e.key == 'reset_score_button' ){
        //alert('i have chosen reset');
        lantern.comm.LanternChannelFactory.ignoreUpdateRequest_ = false;
        lantern.comm.LanternChannelFactory.completed_ = false;
        return;  
      }
      else if ( e.key == 'keep_score_button'){
        //alert('i have chosen to keep scores');
        lantern.comm.LanternChannelFactory.ignoreUpdateRequest_ = true;
        lantern.comm.LanternChannelFactory.completed_ = false;
        return;
      }
    });
   dialog.setVisible(true);
  }
  if ( lantern.comm.LanternChannelFactory.completed_ == true || 
     lantern.comm.LanternChannelFactory.ignoreUpdateRequest_ == true)
  {
  //alert('I am loop33');
     return;
  }
  var obj = goog.json.parse(data)
  var uri = new goog.Uri('/updateScore');
  uri.setParameterValue('widget_id', this.iframeId_);
  uri.setParameterValue('doc_id', this.doc_id_);
  uri.setParameterValue('trunk_id', this.trunk_id_);
  uri.setParameterValue('score', obj.score);
  uri.setParameterValue('progress', obj.progress);
  uri.setParameterValue('absolute', this.absolute_);

  goog.events.removeAll(this.xhr_);
  goog.events.listen(
      this.xhr_, goog.net.EventType.COMPLETE,
      goog.bind(this.processScore, this));
  //alert('sending xhr score\n');
  this.xhr_.send(uri);
};


/**
* Updates data for widget. This is registered as a service.
 * param {string} data Incomming payload.
 * TODO(mukundjha): Write ajax calls to store the data.
 */
lantern.comm.LanternChannel.prototype.updateData = function(data) {
       
};


/**
 * Responds with an updated progress score to the widget.
 * This is registered as a service.
 * param {string} data Incomming payload.
 * TODO(mukundjha): Respond with current data state.
 */
lantern.comm.LanternChannel.prototype.requestScore = function(data) {
	
};


/**
 * Sends associated session_id to the widget.
 * The function is triggred upon completion of AJAX request for
 * session_id.
 */
lantern.comm.LanternChannel.prototype.sendSessionId = function() {
  var obj = this.xhr_.getResponseJson();
  this.channel_.send('process_data', obj.session_id);
};


/**
 * Responds with an updated progress score to the widget.
 * This is registered as a service.
 * param {string} data Incomming payload.
 */
lantern.comm.LanternChannel.prototype.requestData = function(data) {
  
  url = '/getSessionId?widget_id=' + this.iframeId_;
  goog.events.removeAll(this.xhr_);
  goog.events.listen(
      this.xhr_, goog.net.EventType.COMPLETE,
      goog.bind(this.sendSessionId, this));
  this.xhr_.send(url);
};


/**
 * Initializes LanternChannel object by registering required methods.
 */
lantern.comm.LanternChannel.prototype.initializeChannel = function(){
  this.channel_.registerService('update_score',
      goog.bind(this.updateScore, this));
  this.channel_.registerService('update_data',
      goog.bind(this.updateData, this));
  this.channel_.registerService('request_score',
      goog.bind(this.requestScore, this));
  this.channel_.registerService('request_data',
      goog.bind(this.requestData, this));
  this.channel_.connect();
};


/**
 * Factory class for creating LanternChannel objects.
 * @constructor
 */
lantern.comm.LanternChannelFactory = function() {
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
 * Factory method for creating a new channel.
 * To be called in view.html
 * @param {string} thirdPartyBaseUri Base uri for the thirdparty.
 * @param {string} iframeUri Complete uri to be embedded in an iframe.
 * @param {string} iframeContainerId Id of the container of the Iframe.
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
    thirdPartyBaseUri, iframeUri, iframeContainerId, doc_id,
    trunk_id, height, width, absolute, completed) {
   
  lantern.comm.LanternChannelFactory.completed_ = completed;
  lantern.comm.LanternChannelFactory.channelMap_[iframeContainerId] =
  new lantern.comm.LanternChannel(
      thirdPartyBaseUri, iframeUri, iframeContainerId,
      doc_id, trunk_id, height, width, absolute, completed);

  lantern.comm.LanternChannelFactory.channelMap_[
      iframeContainerId].initializeChannel();
};

// On load function to be written in the html after getting iframe information.
