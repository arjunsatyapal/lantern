#!/usr/bin/python
#
# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Class for import/export course outline from the datastore.

Import from yaml:

%YAML 1.2
---
kind: Course
title: AP CS Python
description: >
  An AP-level course for Computer Science using Python
ddc: "000"  # Dewey Decimal
labels:   # Tags
  - AP
  - CS
  - Python
grade_level: 10
is_published: true
creator: test@example.com
creator_id: 09029387462
created: 2010-05-10 12:00
key: alkei20384mp3akk093j+k39nl33
lessons:  # Implicit kink: CourseLesson
  - section_label: Chapter 1
    title: Introduction
    key: ...
    modules:
      - section_label: 1.1
        title: Foo
        key: ...
      - section_label: 1.2
        title: Bar
        key: ...
  - section_label: Chapter 2
    title: Getting Started
    key: ...
    modules:
      ...

"""

# Python imports
import copy
import datetime
import logging
import yaml

# AppEngine imports
from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import users

# Local imports
from demo import models
from demo import model_io


class Error(Exception):
  """Outline module-level errors."""


class InvalidInputError(Error):
  """The input was invalid."""


class CourseOutline(object):
  """Helps load and dump a course outline.

  Currently appropriate for initial load and dump of a course outline.
  It may be useful function to view/manipulate the outline of a course.

  TODO(vchen): Currently only goes to the Module level, but does not handle
  Contents or Exercises of a Module.

  Methods:
    Load(): Loads YAML document from a file-like object or string. May
        contain multiple documents. Returns list of course outlines.
    Dump(): Dumps the outline of a course as a YAML document and returns
        it as a string.

    Store(): Stores the outline of a course into the datastore, making
        sure all the references are set up correctly.
  """

  def __init__(self):
    """Constructs the outline with optional pre-initialized course."""
    self._xcoder = model_io.PedagogyXcoder(model_io.YAML)

  def Load(self, stream):
    """Loads a YAML file that contains an outline and returns a list."""
    data = yaml.safe_load(stream)
    if not isinstance(data, (list, tuple)):
      data = [data]
    courses = []
    for course_dict in data:
      courses.append(self._ParseCourseDict(course_dict))
    return courses

  def Dump(self, course):
    """Dumps a course outline as a YAML document."""
    if not isinstance(course, models.Course):
      raise ValueError("Input arg is not a Course: %r" % course)
    course_dict = self._DumpCourse(course)
    return '%YAML 1.2\n---\n' + yaml.dump(course_dict)

  def Store(self, course):
    """Stores a course outline into the datastore.

    This is most appropriate as a first-time import.

    Authorization must be implemented externally.  Will overwrite entries
    at the same keys.

    TODO(vchen): Need a revision control scheme.
    """
    if not isinstance(course, models.Course):
      raise ValueError("Input arg is not a Course: %r" % course)
    return self._StoreCourse(course)

  # ------- Parse/Load ---------

  def _ParseCourseDict(self, course_dict):
    """Parses a course dictionary loaded via YAML."""
    if 'Course' != course_dict.get('kind'):
      raise InvalidInputError("Input dictionary is not a Course.")

    creator_email = course_dict.get('creator')
    creator_id = course_dict.get('creator_id')
    if creator_email and creator_id:
      creator = users.User(email=creator_email, _user_id=creator_id)
    elif creator_email:
      creator = users.User(email=creator_email)
    else:
      creator = None

    attributes = {
        'creator': creator,
        }
    course, attributes = self._ParseItemDict(
        course_dict, models.Course, attributes)

    # Look for lessons
    lessons = course_dict.get('lessons')
    for ordinal, lesson_dict in enumerate(lessons):
      lesson = self._ParseLessonDict(lesson_dict, attributes)
      section_label = lesson_dict.get('section_label')
      lesson_ref = models.LessonRef(
          ordinal=ordinal,
          section_label=section_label
          )
      lesson_ref._ref = lesson
      course._refs.append(lesson_ref)
    return course

  def _ParseLessonDict(self, lesson_dict, parent_attributes):
    lesson, attributes = self._ParseItemDict(
        lesson_dict, models.CourseLesson, parent_attributes)

    # Look for modules
    modules = lesson_dict.get('modules')
    for ordinal, module_dict in enumerate(modules):
      module = self._ParseModuleDict(module_dict, attributes)
      section_label = module_dict.get('section_label')
      module_ref = models.ModuleRef(
          ordinal=ordinal,
          section_label=section_label
          )
      module_ref._ref = module
      lesson._refs.append(module_ref)
    return lesson

  def _ParseModuleDict(self, module_dict, parent_attributes):
    module, unused_attributes = self._ParseItemDict(
        module_dict, models.LessonModule, parent_attributes)
    # No content and exercises yet.
    return module

  def _ParseItemDict(self, item_dict, item_class, parent_attributes):
    """Parses an item dictionary loaded via YAML.

    Args:
      item_dict: A dictionary loaded for a PedagogyModel instance.
      item_class: The class to instantiate for the item.
      parent_attributes: Parent attributes dict to be inherited.

    Returns:
      A (item, attributes) tuple where item is an instance of the specified
      item_class and attributes is a dict with parsed attributes.
    """
    attributes = copy.copy(parent_attributes)

    # Treat title and description separately, because they should not
    # be inherited.
    title = self._xcoder.DecodeProperty('title', item_dict.get('title'))
    description = self._xcoder.DecodeProperty(
        'description', item_dict.get('description'))

    for attribute in self._xcoder.GetExportedProperties():
      if attribute in ('__key__', 'title', 'description'):
        continue
      value = self._xcoder.DecodeProperty(attribute, item_dict.get(attribute))
      if value is not None:
        attributes[attribute] = value

    item = item_class(
        title=title,
        description=description,
        **attributes)
    key_name = item_dict.get('key')
    if key_name:
      item._kname = key_name
    return item, attributes

  # ------- Dump ---------
  def _DumpCourse(self, course):
    result = self._DumpItem(course)

    # Look for lessons
    lesson_refs = course.get_lessons()
    if lesson_refs:
      lesson_list = result.setdefault('lessons', [])
      for lesson_ref in lesson_refs:
        lesson_dict = self._DumpLesson(lesson_ref.get_reference())
        lesson_dict['section_label'] = lesson_ref.section_label
        lesson_list.append(lesson_dict)
    return result

  def _DumpLesson(self, lesson):
    result = self._DumpItem(lesson)

    # Look for modules
    module_refs = lesson.get_modules()
    if module_refs:
      module_list = result.setdefault('modules', [])
      for module_ref in module_refs:
        module_dict = self._DumpModule(module_ref.get_reference())
        module_dict['section_label'] = module_ref.section_label
        module_list.append(module_dict)
    return result

  def _DumpModule(self, module):
    result = self._DumpItem(module)
    # No content and exercises yet.
    return result

  def _DumpItem(self, item):
    """Returns a property dict for the item."""
    result = {}
    key_name = item._kname
    if item.is_saved():
      key_name = item.key().name()
    if key_name:
      result['key'] = key_name
    properties = item.properties()
    for attribute in self._xcoder.GetExportedProperties():
      prop = properties.get(attribute)
      if not prop:
        continue
      val = prop.get_value_for_datastore(item)
      value = self._xcoder.EncodeProperty(attribute, val)
      if value not in ('', None):
        result[attribute] = value
    return result

  # ------- Store ---------

  def _StoreCourse(self, course):
    """Stores possibly placeholders into the database."""
    # Get list of temporary references
    lesson_refs = course.get_lessons()

    course = self._StoreItem(None, course)
    if lesson_refs:
      for lesson_ref in lesson_refs:
        lesson = self._StoreLesson(course, lesson_ref.get_reference())

        if lesson_ref.parent() != course:
          lesson_ref = models.LessonRef(
              parent=course,
              ordinal=lesson_ref.ordinal,
              section_label=lesson_ref.section_label
              )
        lesson_ref.reference = lesson
        lesson_ref.put()
    return course

  def _StoreLesson(self, parent_course, lesson):
    # Get list of temporary references
    module_refs = lesson.get_modules()

    lesson = self._StoreItem(parent_course.key().name(), lesson)
    lesson.put()
    if module_refs:
      for module_ref in module_refs:
        module = self._StoreModule(lesson, module_ref.get_reference())

        if module_ref.parent() != lesson:
          module_ref = models.ModuleRef(
              parent=lesson,
              ordinal=module_ref.ordinal,
              section_label=module_ref.section_label
              )
        module_ref.reference = module
        module_ref.put()
    return lesson

  def _StoreModule(self, parent_lesson, module):
    module = self._StoreItem(parent_lesson.key().name(), module)
    return module

  def _StoreItem(self, parent_item, item):
    """Stores the specified item.
    - If item has not been saved,
    - If keyname specified, create new one with key
    - Otherwise, create new one with random key, perhaps based on parent
    - Otherwise just put
    """
    item_class = item.__class__
    if item.is_saved():
      item.put()
      return item

    properties = dict(( (prop_name, prop.get_value_for_datastore(item))
                        for (prop_name, prop) in item.properties().iteritems() ))
    if item._kname:
      # TODO(vchen): Need to check for existence?
      new_item = item_class.get_or_insert(item._kname, **properties)
    else:
      key_prefix = None
      num_chars = 32
      if parent_item:
        key_prefix = parent_item.key().name()
        num_chars = 4
      new_item = item_class.insert_with_random_key(
          key_prefix, num_chars, **properties)
    return new_item
