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
 * To be included in iFrame for lantern.
 * IFrame must instantiate LanternWidgetChannel object and call 
 * initializeChannel on the instantiated object.
 *
 * For accessing the channel for obtaining and updating score/data, 
 * IFrame should use following methods on the instantiated object
 * (ex. widgetChannel is the instantiated object):
 *
 * widgetChannel.updateScore
 * widgetChannel.updateData
 * widgetChannel.getScoreAsync
 * widgetChannel.getDataAsync
 *
 * Please see function definition below for description of each method.
 * These methods must be called after initializing the channel.
 */
goog.provide('lantern.widget.LanternWidgetChannel');

goog.require('goog.dom')
goog.require('goog.net.xpc.CrossPageChannel');

/**
 * Constructor for widget channel.
 * @constructor
 *
 * NOTE(mukundjha): 
 *   1) This kind of initialization has problems when the
 *   page refreshes, we need to experiment more.
 */
lantern.widget.LanternWidgetChannel = function() {
  // Get the channel configuration from the URI parameter.
   //alert('creating widget channel with these params:\n'+ 
     // (new goog.Uri(window.location.href)).getParameterValue('xpc'));

  this.cfg_ = goog.json.parse(
      (new goog.Uri(window.location.href)).getParameterValue('xpc'));
  
  this.channel_ = new goog.net.xpc.CrossPageChannel(this.cfg_);
  this.initializeChannel();
  this.activeRequest_ = {};
};


/**
 * Key for getScore.
 * @type string
 * @private
 */
lantern.widget.LanternWidgetChannel.KEY_GET_SCORE_ = 'GET_SCORE';


/**
 * Key for getData.
 * @type string
 * @private
 */
lantern.widget.LanternWidgetChannel.KEY_GET_DATA_ = 'GET_DATA';


/*
 * Function to handle score sent by parent doc.
 * @param {string} data payload sent by the parent doc.
 */
lantern.widget.LanternWidgetChannel.prototype.processScore = function(score) {
  var callback = this.activeRequest_[this.KEY_GET_SCORE_];
  if(callback) { 
    callback(score);
  }
  delete this.activeRequest_[this.KEY_GET_SCORE_];
};


/*
 * Wrapper for exposing channel's send method.
 * @param {string} service Name of the service.	
 * @param {string} opt_payload Optional payload to be passed to the service.
 */
lantern.widget.LanternWidgetChannel.prototype.send = function(
    service, opt_payload) {

  this.channel_.send(service, opt_payload);
};


/*
 * Method to handle 'data' sent by parent doc.
 * @param {string} data payload sent by the parent doc.
 */ 
lantern.widget.LanternWidgetChannel.prototype.processData = function(data) {
  var callback = this.activeRequest_[this.KEY_GET_DATA_];
  if(callback) {
    //alert('has callback');
    callback(data);
  }
  delete this.activeRequest_[this.KEY_GET_DATA_];
};


/**
 *Function to initialize the lanternChannel object.
 */
lantern.widget.LanternWidgetChannel.prototype.initializeChannel = function(callBack) {

  //alert('initializing iframe');
  this.channel_.registerService('process_score',
      goog.bind(this.processScore, this));
  this.channel_.registerService('process_data',
      goog.bind(this.processData, this));
  this.channel_.connect(callBack);
};


/*
 * Function to update score.
 * Wrapper around the native send messages via channels.
 * @param {int} score Score to be sent back to parent doc.
 */
lantern.widget.LanternWidgetChannel.prototype.updateScore = function(score) {
  //alert('sending score' + this.channel_.name);
  this.channel_.send('update_score', score);
};


/*
 * Function to update data.
 * Wrapper around the native send messages via channels.
 * @param {string} data Data in string format(JSON) to be sent back to
 * parent doc.
 */
lantern.widget.LanternWidgetChannel.prototype.updateData = function(data) {
  //alert('sending data' + this.channel_.isConnected());
  this.channel_.send('update_data', data);
};


/*
 * Function to get data.
 * Wrapper around the native send messages via channels.
 * parent doc.
 * @param {function} reportDataCallBack Callback function to handle the 
 * data when it arrives.
 */
lantern.widget.LanternWidgetChannel.prototype.getScoreAsync = 
    function(reportScoreCallback) {

  this.activeRequest_[this.KEY_GET_SCORE_] = reportScoreCallback;
  this.channel_.send('request_score');
};


/*
 * Function to get score.
 * Wrapper around the native send messages via channels.
 * parent doc.
 * @param {function} reprotScoreCallback Callback function to handle the 
 * score when it arrives.
 */
lantern.widget.LanternWidgetChannel.prototype.getDataAsync = 
    function(reportDataCallback) {
  this.activeRequest_[this.KEY_GET_DATA_] = reportDataCallback;
  this.channel_.send('request_data');
};
