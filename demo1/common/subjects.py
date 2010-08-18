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

"""Subject Taxonomy.

Methods:
  GetSubjectsTaxonomy(): Factory method that returns an instance of
      SubjectTaxonomy.  It current loads data from subjects.yaml.
  GetSubjectsJson(): To get a JSON representation of a subject's descendents.
"""

import os
import yaml
from django.utils import simplejson


class SubjectItem(object):
  """Represents a subject item.

  Attributes:
    subject_id: The ID of the subject. This is the identity of the subject
        that should be unique.
    name: Name of the subject that is to be displayed. If empty, it is set to
        subject_id.
  """

  def __init__(self, subject_id, name=None):
    self.subject_id = subject_id
    self.name = name or subject_id


class SubjectTaxonomy(object):
  """Taxonomy of subject material.

  The taxonomy is maintained as dictionaries describing child/parent
  relationshipts.

  Attributes:
    _roots: List of SubjectItems that are the roots.
    _item_map: Maps subject ID to SubjectItem.
    _children_map: Maps subject ID to list of SubjectItem.
    _parent_map: Maps subject ID to parent ID.
  """

  def __init__(self):
    self._roots = []
    self._item_map = {}
    self._children_map = {}
    self._parent_map = {}

  def GetSubject(self, subject_id):
    """Gets a subject by subject_id.

    Args:
      subject_id: ID of the subject.
    Returns:
      A SubjectItem, if found; otherwise returns None.
    """
    return self._item_map.get(subject_id)

  def GetChildSubjects(self, subject_id):
    """Gets a list of child subjects for the specified subject.

    Args:
      subject_id: ID of the subject. If empty, get the roots.
    Returns:
      A list of SubjectItems. May return None if not found.
    """
    if subject_id:
      return self._children_map.get(subject_id)
    else:
      return self._roots

  def GetParent(self, subject_id):
    """Gets the parent subject for the specified ID.

    Args:
      subject_id: ID of the subject.
    Returns:
      A SubjectItem representing the parent. Returns None if the subject is
      a root item.
    """
    if subject_id:
      parent_id = self._parent_map.get(subject_id)
      if parent_id:
        return self._item_map.get(parent_id)
    return None

  def AddSubject(self, subject, parent_id):
    """Adds a subject item.

    Args:
      subject: A SubjectItem to be added.
      parent_id: The ID of the parent. May be None if it is a root subject.
    """
    self._item_map[subject.subject_id] = subject
    if not parent_id:
      self._roots.append(subject)
    else:
      children = self._children_map.setdefault(parent_id, [])
      children.append(subject)
      self._parent_map[subject.subject_id] = parent_id

  def IsLeafSubject(self, subject_id):
    """Returns whether specified subject is a leaf."""
    children = self._children_map.get(subject_id)
    return children is None


# Singleton of taxonomy.
_taxonomy = None


def _GetSubjectsTaxonomyFromYaml(fileObj):
  """Factory method for getting the taxonomy.

  Current implementation loads from a file.

  Args:
    fileObj: A file-like object from which to load the YAML data

  Returns:
    An instance of SubjectTaxonomy.
  """
  data = yaml.safe_load(fileObj)

  # Convert into internal representation.
  taxonomy = SubjectTaxonomy()
  for parent_id, subject_list in data.iteritems():
    for subject_id in subject_list:
      if parent_id == 'root':
        taxonomy.AddSubject(SubjectItem(subject_id), None)
      else:
        taxonomy.AddSubject(SubjectItem(subject_id), parent_id)
  return taxonomy


def GetSubjectsTaxonomy(force=False):
  """Factory method for getting the taxonomy.

  Current implementation loads from a file.

  Args:
    force: If true, will reload data, even when it's already loaded. Default
        is False.

  Returns:
    An instance of SubjectTaxonomy.
  """
  global _taxonomy
  if _taxonomy and not force:
    return _taxonomy

  fname = os.path.join(os.path.dirname(__file__), 'subjects.yaml')
  fileObj = open(fname, "r")
  _taxonomy = _GetSubjectsTaxonomyFromYaml(fileObj)
  return _taxonomy


def _ToDict(taxonomy, subject_id, levels, result=None):
  """Converts taxonomy to dict of lists. Recursive.

  The dict is of the form:

   {subject_id: [child_subject, ...],
    ...
   }

  The root node is explicitly represented as 'root', rather than None.

  Each child subject is a dict of the form:

   {i: id, n: name, l: isLeaf}

  Args:
    taxonomy: An instance of SubjectTaxonomy.
    subject_id: The ID of the subject to convert to JSON.
    levels: The number of levels to convert.
    result: The result dict to use for output. If None (default) a new one
        is created and returned.

  Returns:
    The dict that represents the accumulated result.
  """
  result = result or {}
  subjects = taxonomy.GetChildSubjects(subject_id)
  if subjects:
    subjects_as_dict = [
        dict(i=s.subject_id, n=s.name, l=taxonomy.IsLeafSubject(s.subject_id))
        for s in subjects]
    if subject_id:
      result[subject_id] = subjects_as_dict
    else:
      result['root'] = subjects_as_dict

  # Recurse, if needed.
  levels -= 1
  if levels and subjects:
    for subject in subjects:
      _ToDict(taxonomy, subject.subject_id, levels, result)
  return result


def GetSubjectsJson(taxonomy, subject_id, levels=2):
  """Converts taxonomy to JSON as a two-element list:

  [subject_id, subjects_dict]

  Args:
    taxonomy: An instance of SubjectTaxonomy.
    subject_id: The ID of the subject to convert ot JSON.
    levels: The number of levels to convert. Default is 2.

  Returns:
    A string that is the JSON serialization of [subject_id, subjects_dict].
  """
  result = _ToDict(taxonomy, subject_id, levels)
  return simplejson.dumps([subject_id, result])


if __name__ == '__main__':
  # Quick command-lne tests
  t = GetSubjectsTaxonomy()
  print t
  print GetSubjectsJson(t, None)
  print GetSubjectsJson(t, 'technology')
