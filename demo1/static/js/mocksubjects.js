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
 * @fileoverview Mock implementation of SubjectProvider to return a set of
 *     subject items.
 */
goog.provide('lantern.subject.MockSubjectProvider');

goog.require('lantern.subject.SubjectItem');
goog.require('lantern.subject.SubjectProvider');



/**
 * Mock provider with hard-coded subjects.
 *
 * @constructor
 * @extends {lantern.subject.SubjectProvider}
 */
lantern.subject.MockSubjectProvider = function() {
  lantern.subject.SubjectProvider.call(this);

  // Roots
  var subjects = lantern.subject.MockSubjectProvider.ROOT_SUBJECTS_;
  for (var i = 0; i < subjects.length; i++) {
    this.treeModel_.addSubject(
        new lantern.subject.SubjectItem(subjects[i], null),
        null);
  }

  subjects = lantern.subject.MockSubjectProvider.TECHNOLOGY_SUBJECTS_;
  for (var i = 0; i < subjects.length; i++) {
    this.treeModel_.addSubject(
        new lantern.subject.SubjectItem(subjects[i], null),
        'technology');
  }

  subjects = lantern.subject.MockSubjectProvider.ENGINEERING_SUBJECTS_;
  for (var i = 0; i < subjects.length; i++) {
    this.treeModel_.addSubject(
        new lantern.subject.SubjectItem(subjects[i], null),
        'engineering');
  }

  subjects = lantern.subject.MockSubjectProvider.SOFTWARE_SUBJECTS_;
  for (var i = 0; i < subjects.length; i++) {
    this.treeModel_.addSubject(
        new lantern.subject.SubjectItem(subjects[i], null),
        'software/computation');
  }

  subjects = lantern.subject.MockSubjectProvider.PROGRAMMING_SUBJECTS_;
  for (var i = 0; i < subjects.length; i++) {
    this.treeModel_.addSubject(
        new lantern.subject.SubjectItem(subjects[i], null, true /* isLeaf */),
        'programming languages');
  }
};
goog.inherits(lantern.subject.MockSubjectProvider,
              lantern.subject.SubjectProvider);

/**
 * Root entries.
 * @type Array.<string>
 * @private
 */
lantern.subject.MockSubjectProvider.ROOT_SUBJECTS_ = [
    'math',
    'technology',
    'communication',
    'health',
    'money',
    'society',
    'sports & recreation',
    'hobby',
    'misc'
    ];

/**
 * Technology entries.
 * @type Array.<string>
 * @private
 */
lantern.subject.MockSubjectProvider.TECHNOLOGY_SUBJECTS_ = [
    'physics',
    'chemistry',
    'bioogy',
    'geology',
    'medicine',
    'engineering'
    ];

/**
 * Engineering entries.
 * @type Array.<string>
 * @private
 */
lantern.subject.MockSubjectProvider.ENGINEERING_SUBJECTS_ = [
    'mechanical',
    'electrical',
    'chemical',
    'aeronautical',
    'genetic',
    'software/computation',
    'food',
    'textiles',
    'education'
    ];


/**
 * Software entries.
 * @type Array.<string>
 * @private
 */
lantern.subject.MockSubjectProvider.SOFTWARE_SUBJECTS_ = [
    'introduction to computer programming',
    'algorithms & data structures',
    'abstraction',
    'programming languages',
    'operating systems',
    'compilers',
    'complexity management, teamwork, and revision control',
    'storage, data structures, and databases',
    'memory architectures and coping with latency',
    'data communication, networks and routing'
    ];


/**
 * Programming entries.
 * @type Array.<string>
 * @private
 */
lantern.subject.MockSubjectProvider.PROGRAMMING_SUBJECTS_ = [
    'C',
    'BASIC',
    'C++',
    'ECMAScript derivatives',
    'FORTRAN',
    'Haskell',
    'Java',
    'Lisp',
    'Modula',
    'Pascal',
    'Prolog',
    'Python',
    'Scheme',
    'Simula',
    'Smalltalk'
    ];
