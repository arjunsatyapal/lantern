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
 * @fileoverview Data structure for subject items and interface for getting
 *     a collection of subjects.
 */

goog.provide('lantern.subject.SubjectItem');
goog.provide('lantern.subject.SubjectTreeModel');
goog.provide('lantern.subject.SubjectProvider');

goog.require('goog.events.EventTarget');
goog.require('goog.structs');
goog.require('goog.structs.Map');



/**
 * Simple struct for holding attributes of a subject item.
 *
 * @param {string} id Id of the subject item.
 * @param {string?} displayText Display string of the subject item. No HTML.
 *     If null, uses id.
 * @param {boolean} opt_isLeaf Whether it is a leaf item.
 * @constructor
 */
lantern.subject.SubjectItem = function(id, displayText, opt_isLeaf) {
  /**
   * ID string for the subject item.
   * @type string
   */
  this.id = id;

  /**
   * Display text for the item. If null, set it to be the same as id.
   * @type string
   */
  this.displayText = displayText ? displayText : id;

  /**
   * Whether this item is a leaf.
   * @type boolean
   */
  this.isLeaf = opt_isLeaf ? true : false;
};



/**
 * Model for representing a hierarchical tree of subject items.
 *
 * @constructor
 */
lantern.subject.SubjectTreeModel = function() {

  /**
   * Roots of the subject tree.
   * @type Array.<lantern.subject.SubjectItem>
   * @private
   */
  this.roots_ = [];

  /**
   * Map of ID to its corresponding SubjectItem.
   * @type goog.structs.Map
   * @private
   */
  this.itemMap_ = new goog.structs.Map();

  /**
   * Map of SubjectItem to its children. Maps ID string to array of SubjectItems.
   * @type goog.structs.Map
   */
  this.childrenMap_ = new goog.structs.Map();

  /**
   * Map of SubjectItem ID to its parent ID.
   * @type goog.structs.Map
   * @private
   */
  this.parentMap_ = new goog.structs.Map();
};


/**
 * Gets the subject for the ID.
 *
 * @param {string} id ID of the subject to find.
 * @return {lantern.subject.SubjectItem?} The subject item or undefined if not
 *     found.
 */
lantern.subject.SubjectTreeModel.prototype.getSubject = function(id) {
  return /** @type lantern.subject.SubjectItem */(this.itemMap_.get(id));
};


/**
 * Returns a list of subjects for the specified parent.
 *
 * @param {string|null} id ID of the parent node for which to get items.
 * @return {Array.<lantern.subject.SubjectItem>?} Array of items.
 */
lantern.subject.SubjectTreeModel.prototype.getChildSubjects = function(id) {
  if (id) {
    return /** @type lantern.subject.SubjectItem */(this.childrenMap_.get(id));
  } else {
    return (!!this.roots_ ? this.roots_ : undefined);
  }
};


/**
 * Returns the parent of the specified subject item.
 *
 * @param {string} id ID of the subject item.
 * @return {lantern.subject.SubjectItem?} Parent SubjectItem, if found;
 *     undefined otherwise.
 */
lantern.subject.SubjectTreeModel.prototype.getParent = function(id) {
  if (id) {
    var parentId = this.parentMap_.get(id);
    if (parentId) {
      return this.itemMap_.get(parentId);
    }
  }
  return undefined;
};


/**
 * Adds a SubjectItem to the tree.
 *
 * @param {lantern.subject.SubjectItem} item A SubjectItem to add to the tree.
 * @param {string?} parentId ID of the parent. Use null for root items.
 */
lantern.subject.SubjectTreeModel.prototype.addSubject = function(
    item, parentId) {
  this.itemMap_.set(item.id, item);
  if (!parentId) {
    this.roots_.push(item);
  } else {
    var children = this.childrenMap_.get(parentId);
    if (!children) {
      children = [];
      this.childrenMap_.set(parentId, children);
    }
    children.push(item);
    this.parentMap_.set(item.id, parentId);
  }
};


/**
 * Clears internal data structures.
 */
lantern.subject.SubjectTreeModel.prototype.clear = function() {
  this.roots_ = [];
  this.itemMap_.clear();
  this.childrenMap_.clear();
  this.parentMap_.clear();
}


/**
 * Gets the number of subjects.
 * @return {number} Count of items.
 */
lantern.subject.SubjectTreeModel.prototype.getCount = function() {
  return this.itemMap_.getCount();
};


/**
 * Returns whether the model is empty.
 * @return {boolean} True if there are no items.
 */
lantern.subject.SubjectTreeModel.prototype.isEmpty = function() {
  return this.itemMap_.isEmpty();
};



/**
 * Abstract base class for a provider of SubjectTreeModel.  Derived classes must
 * provide a way to populate the tree.
 *
 * @constructor
 * @extends {goog.events.EventTarget}
 */
lantern.subject.SubjectProvider = function() {
  goog.events.EventTarget.call(this);

  /**
   * Internal model for a tree of subject items.
   * @type {lantern.subject.SubjectTreeModel}
   */
  this.treeModel_ = new lantern.subject.SubjectTreeModel();
};
goog.inherits(lantern.subject.SubjectProvider, goog.events.EventTarget);


/**
 * Event types for the provider.
 * @enum {string}
 */
lantern.subject.SubjectProvider.EventType = {

  /** When the loaded data is ready. */
  DATA_READY: 'data_ready',

  /** When the loaded data resulted in error. */
  DATA_ERROR: 'data_error'
};


/**
 * Returns the subject item for the specified ID.
 *
 * @param {string|null} id ID of the subject item.
 * @return {lantern.subject.SubjectItem?} A subjet item.
 */
lantern.subject.SubjectProvider.prototype.getSubject = function(id) {
  return this.treeModel_.getSubject(id);
};


/**
 * Returns the parent of the subject item.
 *
 * @param {string} id ID of the subject item.
 * @return {lantern.subject.SubjectItem?} The parent subjet item or undefined;
 */
lantern.subject.SubjectProvider.prototype.getParent = function(id) {
  return this.treeModel_.getParent(id);
};


/**
 * Returns a list of subjects for the specified parent.
 *
 * @param {string?} id ID of the parent node for which to get items. If null,
 *     get the root items.
 * @return {Array.<lantern.subject.SubjectItem>} Array of subject items.
 *     id and item array:
 *
 */
lantern.subject.SubjectProvider.prototype.getChildSubjects = function(
    id, opt_callback) {
  return this.treeModel_.getChildSubjects(id);
};


/**
 * Request to load data for the specified subject.
 * By default, immediately dispatches the
 * lantern.subject.SubjectProver.Event.LOAD event.
 *
 * @param {string?} id ID of the subject to load. If null, load the root items.
 */
lantern.subject.SubjectProvider.prototype.loadSubjects = function(id) {
  this.dispatchEvent(lantern.subject.SubjectProvider.EventType.DATA_READY);
};
