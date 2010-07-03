# !/usr/bin/python
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

"""Tests for the Lantern library functions."""

# Python imports
import logging
import unittest
import os

# AppEngine imports
from google.appengine.ext import db
from google.appengine.api import users

# local imports
from demo import library
from demo import models
import settings

ROOT_PATH = settings.ROOT_PATH
_INVALID_FILE_PATH = os.path.join(ROOT_PATH, "non-existent-file")
_INVALID_YAML_FILE = os.path.join(ROOT_PATH, "invalid-yaml-file")
_INVALID_NODE_FILE = os.path.join(ROOT_PATH, "valid-leaf-file")
_INVALID_LEAF_FILE = os.path.join(ROOT_PATH, "valid-node-file")
_VALID_NODE_FILE = os.path.join(ROOT_PATH, "valid-node-file")
_VALID_LEAF_FILE = os.path.join(ROOT_PATH, "valid-leaf-file")


class InsertWithNewKeyTest(unittest.TestCase):
  """Test insertion of object with new random key.

  TODO(mukundjha): Add test cases for function insert_with_new_key.
  """

class GetDocForUserTest(unittest.TestCase):
  """Test fetching document based on user's state.

  If trunk_id has an entry in user's state, return the last document visited
  in the trunk, else return the latest document in the trunk.
  """

  def testFetchWithTrunkEntry(self):
    trunk = library.insert_with_new_key(models.TrunkModel)
    doc1 = library.create_new_doc(trunk.key())
    doc2 = library.create_new_doc(trunk.key())

    library.insert_with_new_key(models.DocVisitState, trunk_ref=trunk,
      doc_ref = doc1)
    doc = library.get_doc_for_user(trunk.key(), users.get_current_user())
    self.assertEquals(str(doc.key()), str(doc1.key()))

  def testFetchWithNoEntry(self):
    trunk = library.insert_with_new_key(models.TrunkModel)
    doc1 = library.create_new_doc(trunk.key())
    doc2 = library.create_new_doc(trunk.key())

    doc = library.get_doc_for_user(trunk.key(), users.get_current_user())
    self.assertEquals(str(doc.key()), str(doc2.key()))

  def testDifferentUsersView(self):
    trunk = library.insert_with_new_key(models.TrunkModel)
    doc1 = library.create_new_doc(trunk.key())
    doc2 = library.create_new_doc(trunk.key())
    doc3 = library.create_new_doc(trunk.key())

    new_user1 = users.User('test1@gmail.com')
    library.insert_with_new_key(models.DocVisitState, trunk_ref=trunk,
      doc_ref = doc1, user=new_user1)
    new_user2 = users.User('test2@gmail.com')
    library.insert_with_new_key(models.DocVisitState, trunk_ref=trunk,
      doc_ref = doc2, user=new_user2)

    new_user3 = users.User('test3@gmail.com')
    doc = library.get_doc_for_user(trunk.key(), new_user1)
    self.assertEquals(str(doc.key()), str(doc1.key()))
    doc = library.get_doc_for_user(trunk.key(), new_user2)
    self.assertEquals(str(doc.key()), str(doc2.key()))
    doc = library.get_doc_for_user(trunk.key(), new_user3)
    self.assertEquals(str(doc.key()), str(doc3.key()))
    doc = library.get_doc_for_user(trunk.key(), None)
    self.assertEquals(str(doc.key()), str(doc3.key()))

  def testFetchWithInvalidInput(self):
    self.assertRaises(models.InvalidTrunkError, library.get_doc_for_user, 'xx',
      users.get_current_user())


class GetParentTest(unittest.TestCase):
  """Test for fetching parent for a doc."""

  def testDocWithNoParent(self):
    doc1 = library.create_new_doc()
    doc = library.get_parent(doc1.key())
    self.assertEquals(None, doc)

  def testDocWithSingleParent(self):
    doc1 = library.create_new_doc()
    doc2 = library.create_new_doc()

    library.insert_with_new_key(models.DocLinkModel,
      trunk_ref=doc1.trunk_ref.key(), doc_ref=doc1.key(),
      from_trunk_ref=doc2.trunk_ref.key(), from_doc_ref=doc2.key())

    doc = library.get_parent(doc1)
    self.assertEquals(str(doc2.key()), str(doc.key()))

  def testDocWithMultipleParents(self):
    """Test that latest parent should be returned.

    This would eventually return highest ranked parent.
    """
    doc1 = library.create_new_doc()
    doc2 = library.create_new_doc()
    doc3 = library.create_new_doc()
    library.insert_with_new_key(models.DocLinkModel, trunk_ref=doc1.trunk_ref.key(),
      doc_ref=doc1.key(), from_trunk_ref=doc3.trunk_ref.key(),
      from_doc_ref=doc3.key())

    library.insert_with_new_key(models.DocLinkModel, trunk_ref=doc1.trunk_ref.key(),
      doc_ref=doc1.key(), from_trunk_ref=doc2.trunk_ref.key(),
      from_doc_ref=doc2.key())

    doc = library.get_parent(doc1)
    self.assertEquals(str(doc2.key()), str(doc.key()))


class GetAccumulatedScoreTest(unittest.TestCase):
  """Test retrieving accumulated progress score for a document."""

  def testDocWithNoContent(self):
    doc = library.create_new_doc()
    score = doc.get_score(users.get_current_user())
    self.assertEquals(0, score)

  def testDocWithContent(self):
    # creating a doc
    doc = library.create_new_doc()
    # registering score for doc
    library.insert_with_new_key(models.DocVisitState, trunk_ref=doc.trunk_ref,
      doc_ref = doc, user=users.get_current_user(), progress_score=4)
    # creating another doc
    doc1 = library.create_new_doc()
    # creating link to previous doc
    link = library.insert_with_new_key(models.DocLinkModel, trunk_ref=doc.trunk_ref.key(),
      doc_ref=doc.key(), from_trunk_ref=doc1.trunk_ref.key(),
      from_doc_ref=doc1.key())
    # creating a quiz
    quiz = library.insert_with_new_key(models.QuizModel,
      quiz_url='http://quiz')
    # registering score for quiz
    library.insert_with_new_key(models.QuizProgressState, quiz_ref=quiz,
      user=users.get_current_user(), progress_score=8)
    # adding link and quiz to doc
    doc1.content.append(link.key())
    doc1.content.append(quiz.key())
    doc1.put()
    doc_content = library.get_doc_contents(doc1)

    score = library.get_accumulated_score(doc1, doc_content, users.get_current_user())
    # avg score
    self.assertEquals(6, score)
    # checking if score is registered
    score_for_doc = doc1.get_score(users.get_current_user())
    self.assertEquals(6, score_for_doc)


class AppendToTrunkTest(unittest.TestCase):
  """Test appending document to trunk."""

  def testAppendWithInvalidIds(self):
    self.assertRaises(TypeError, library.append_to_trunk)
    self.assertRaises(models.InvalidTrunkError, library.append_to_trunk,
      'Invalid', 'Invalid')

  def testAppendWithInvalidTrunkId(self):
    doc = library.insert_with_new_key(models.DocModel)
    self.assertRaises(models.InvalidTrunkError, library.append_to_trunk,
      'Invalid', str(doc.key()))

  def testAppendWithInvalidDocId(self):
    trunk = library.insert_with_new_key(models.TrunkModel)
    doc = library.insert_with_new_key(models.DocModel)
    self.assertRaises(TypeError, library.append_to_trunk,
      str(trunk.key()))

  def testAppendToNewTrunk(self):
    trunk = library.insert_with_new_key(models.TrunkModel)
    doc = library.insert_with_new_key(models.DocModel)

    trunk_revisions = models.TrunkRevisionModel.all().ancestor(trunk)
    self.assertEquals(trunk_revisions.count(), 0)

    returned_trunk = library.append_to_trunk(trunk.key(), str(doc.key()))

    trunk_revision_entry = models.TrunkRevisionModel.all().ancestor(trunk).get()
    self.assertEquals(str(trunk_revision_entry.parent().key()),
      str(trunk.key()))
    self.assertEquals(str(trunk_revision_entry.obj_ref), str(doc.key()))

    updated_trunk = db.get(trunk.key())
    self.assertEquals(str(updated_trunk.head), str(doc.key()))

  def testAppendToExistingTrunk(self):
    trunk = library.insert_with_new_key(models.TrunkModel)
    doc = library.insert_with_new_key(models.DocModel)

    trunk_revision1 = library.insert_with_new_key(models.TrunkRevisionModel,
      parent=trunk, obj_ref=str(doc.key()), commit_message='Test message')
    doc2 = library.insert_with_new_key(models.DocModel)

    trunk_revisions = models.TrunkRevisionModel.all().ancestor(trunk)
    self.assertEquals(trunk_revisions.count(), 1)

    returned_trunk = library.append_to_trunk(trunk.key(), str(doc2.key()))

    trunk_revision_entry = models.TrunkRevisionModel.all().ancestor(trunk)

    self.assertEquals(trunk_revisions.count(), 2)

    trunk_revision = models.TrunkRevisionModel.all().ancestor(trunk).order(
      '-time_stamp').fetch(1)
    self.assertEquals(str(trunk_revision[0].parent().key()), str(trunk.key()))
    self.assertEquals(str(trunk_revision[0].obj_ref), str(doc2.key()))

    updated_trunk = db.get(trunk.key())
    self.assertEquals(str(updated_trunk.head), str(doc2.key()))


class CreateNewTrunkWithDocTest(unittest.TestCase):
  """Test creation of a new trunk with passed doc as head."""

  def testCreationWithNoDocId(self):
    self.assertRaises(TypeError, library.create_new_trunk_with_doc)

  def testValidCreation(self):
    doc = library.insert_with_new_key(models.DocModel)
    trunk = library.create_new_trunk_with_doc(str(doc.key()))

    self.assertEquals(str(trunk.head), str(doc.key()))

    trunk_revisions = models.TrunkRevisionModel.all()
    self.assertEquals(trunk_revisions.count(), 1)

    trunk_revision = models.TrunkRevisionModel.all().get()

    self.assertEquals(str(trunk_revision.parent().key()), str(trunk.key()))
    self.assertEquals(str(trunk_revision.obj_ref), str(doc.key()))


class CreateNewDocTest(unittest.TestCase):
  """Test insertion of new doc."""

  def testInsertWithValidTrunkId(self):
    # creating a trunk
    trunk = library.insert_with_new_key(models.TrunkModel)
    doc = library.create_new_doc(trunk.key())

    self.assertEquals(str(doc.trunk_ref.key()), str(trunk.key()))

    trunk = db.get(trunk.key())
    head = db.get(trunk.head)

    revisions = models.TrunkRevisionModel.all().ancestor(trunk)

    self.assertEquals(str(head.key()), str(doc.key()))
    self.assertEquals(revisions.count(), 1)

    returned_doc = revisions.fetch(1)
    self.assertEquals(str(returned_doc[0].obj_ref), str(doc.key()))

  def testInsertWithInvalidTrunkId(self):

    self.assertRaises(models.InvalidTrunkError, library.create_new_doc,
      "xxxx")

  def testInsertWithNoTrunkId(self):
    doc = library.create_new_doc()
    trunk = db.get(doc.trunk_ref.key())

    head = db.get(trunk.head)


    revisions = models.TrunkRevisionModel.all().ancestor(trunk)

    self.assertEquals(str(head.key()), str(doc.key()))
    self.assertEquals(revisions.count(), 1)

    returned_revision = revisions.fetch(1)
    self.assertEquals(returned_revision[0].obj_ref, str(doc.key()))


class FetchDocTest(unittest.TestCase):
  """Test for fetching document from datastore.

  If no trunk_id or invalid trunk_id raise InvaildDocumentError
  If both trunk_id and doc_id are provided retrieve the corresponding
  document.
  If doc_id is invalid or only trunk_id is provided retrieve head document
  for the trunk.

  TODO(mukundjha): Check for raised exceptions.
  """

  def testInvalidTrunkId(self):
    self.assertRaises(models.InvalidTrunkError, library.fetch_doc, "InvalidID",
      "InvalidId")
    self.assertRaises(models.InvalidTrunkError, library.fetch_doc, "InvalidID")
    self.assertRaises(TypeError, library.fetch_doc)

  def testValidTrunkIdAndInvalidDocId(self):
    doc_rev1 = library.create_new_doc()
    trunk_ref = doc_rev1.trunk_ref
    trunk = db.get(trunk_ref.key())
    new_doc_rev1 = library.create_new_doc()

    self.assertRaises(models.InvalidDocumentError, library.fetch_doc,
      str(trunk_ref.key()), str(new_doc_rev1.key()))
    self.assertRaises(models.InvalidDocumentError, library.fetch_doc,
      str(trunk_ref.key()), "xxx")

  def testVaildTrunkIdAndNoDocId(self):
    doc_rev1 = library.create_new_doc()
    trunk_ref = doc_rev1.trunk_ref
    # creating a new doc with same trunk id
    doc_rev2 = library.create_new_doc(str(trunk_ref.key()))

    doc2 = library.fetch_doc(str(trunk_ref.key()))
    trunk = db.get(trunk_ref.key())
    self.assertEqual(str(doc2.key()), str(doc_rev2.key()))

  def testFetchSpecificDocWithDocID(self):
    doc_rev1 = library.create_new_doc()
    trunk_ref = doc_rev1.trunk_ref
    # creating a new doc with same trunk id
    doc_rev2 = library.create_new_doc(str(trunk_ref.key()))

    doc2 = library.fetch_doc(str(trunk_ref.key()), str(doc_rev1.key()))

    self.assertEqual(str(doc2.key()), str(doc_rev1.key()))


class ParseYamlTest(unittest.TestCase):
  """Tests for parse_yaml function."""

  def testLoadInvalidFilePath(self):
    data_dict = library.parse_yaml(_INVALID_FILE_PATH)
    self.assertEquals(1, len(data_dict))
    self.assertTrue('errorMsg' in data_dict)

  def testLoadInvalidFile(self):
    data_dict = library.parse_yaml(_INVALID_YAML_FILE)
    self.assertEquals(1, len(data_dict))
    self.assertTrue('errorMsg' in data_dict)

  def testLoadValidFile(self):
    data_dict = library.parse_yaml(_VALID_NODE_FILE)
    self.assertFalse('errorMsg' in data_dict)
    self.assertEquals(9, len(data_dict))
    self.assertEquals("group", data_dict.get('doc_type'))
    self.assertEquals("Course", data_dict.get('doc_type_desc'))
    self.assertEquals("DUdpMQXAZewtzPdkLtwW6K", data_dict.get('doc_key'))
    self.assertEquals("AP CS Python", data_dict.get('doc_title'))
    self.assertEquals("2010-05-27 10:15", data_dict.get('doc_created_on'))
    self.assertEquals("mukundjha@google.com", data_dict.get('doc_creator'))
    self.assertEquals(['p1', 'p2', 'p3'], data_dict.get('doc_parents'))
    self.assertEquals(2, len(data_dict.get('doc_content')))
    self.assertEquals("AlRG3wQOBqMc2nIwjoHZZ8",
    data_dict.get('doc_content')[0]['key'])

    self.assertEquals("Overview of AP CS Learning with Python",
    data_dict.get('doc_content')[0]['title'])

    self.assertEquals("g", data_dict.get('doc_content')[0]['type'])
    self.assertEquals("BQYVV1KayQ2xjccQgIXfP+",
    data_dict.get('doc_content')[1]['key'])

    self.assertEquals("The way of the program",
    data_dict.get('doc_content')[1]['title'])

    self.assertEquals("g", data_dict.get('doc_content')[1]['type'])


class ParseNodeTest(unittest.TestCase):
  """Tests for parse node function."""

  def testLoadInvaildNodePath(self):
    data_dict = library.parse_node(_INVALID_FILE_PATH)
    self.assertEquals(1, len(data_dict))
    self.assertTrue('errorMsg' in data_dict)

  def testLoadInvaildFilePath(self):
    data_dict = library.parse_node(_VALID_LEAF_FILE)
    self.assertEquals(1, len(data_dict))
    self.assertTrue('errorMsg' in data_dict)

  def testLoadValidFile(self):
    data_dict = library.parse_node(_VALID_NODE_FILE)
    self.assertFalse('errorMsg' in data_dict)
    self.assertEquals(9, len(data_dict))
    self.assertEquals("group", data_dict.get('doc_type'))
    self.assertEquals("Course", data_dict.get('doc_type_desc'))
    self.assertEquals("DUdpMQXAZewtzPdkLtwW6K", data_dict.get('doc_key'))
    self.assertEquals("AP CS Python", data_dict.get('doc_title'))
    # self.assertEquals("AP AP course on Python", data_dict.get('doc_desc'))
    self.assertEquals("2010-05-27 10:15", data_dict.get('doc_created_on'))
    self.assertEquals("mukundjha@google.com", data_dict.get('doc_creator'))
    self.assertEquals(['p1', 'p2', 'p3'], data_dict.get('doc_parents'))
    self.assertEquals(2, len(data_dict.get('doc_content')))

    self.assertEquals("AlRG3wQOBqMc2nIwjoHZZ8",
    data_dict.get('doc_content')[0]['key'])

    self.assertEquals("Overview of AP CS Learning with Python",
    data_dict.get('doc_content')[0]['title'])

    self.assertEquals("g", data_dict.get('doc_content')[0]['type'])
    self.assertEquals("BQYVV1KayQ2xjccQgIXfP+",
    data_dict.get('doc_content')[1]['key'])
    self.assertEquals("The way of the program",
    data_dict.get('doc_content')[1]['title'])

    self.assertEquals("g", data_dict.get('doc_content')[1]['type'])


class ParseLeafTest(unittest.TestCase):
  """Tests for parse_leaf function."""

  def testLoadInvaildLeafPath(self):
    data_dict = library.parse_leaf(_INVALID_FILE_PATH)
    self.assertEquals(1, len(data_dict))
    self.assertTrue('errorMsg' in data_dict)

  def testLoadInvaildFilePath(self):
    data_dict = library.parse_leaf(_VALID_NODE_FILE)
    self.assertEquals(1, len(data_dict))
    self.assertTrue('errorMsg' in data_dict)

  def testLoadValidFile(self):
    data_dict = library.parse_leaf(_VALID_LEAF_FILE)
    self.assertFalse('errorMsg' in data_dict)
    self.assertEquals(9, len(data_dict))
    self.assertEquals("content", data_dict.get('doc_type'))
    self.assertEquals("module", data_dict.get('doc_type_desc'))
    self.assertEquals("CE9+naE8SU6kMS05xno8Qg", data_dict.get('doc_key'))
    self.assertEquals("Values and types", data_dict.get('doc_title'))
    # self.assertEquals("AP AP course on Python", data_dict.get('doc_desc'))
    self.assertEquals("2010-05-27 10:15", data_dict.get('doc_created_on'))
    self.assertEquals("mukundjha@google.com", data_dict.get('doc_creator'))
    self.assertEquals(['p1', 'p2', 'p3'], data_dict.get('doc_parents'))
    self.assertEquals("This is a message", data_dict.get('doc_content'))


if __name__ == "__main__":
  unittest.main()
