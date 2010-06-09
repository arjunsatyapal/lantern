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

"""Dewey Decimal Classification (DDC).

http://en.wikipedia.org/wiki/List_of_Dewey_Decimal_classes#\
  000_.E2.80.93_Computer_science.2C_information_.26_general_works

Imported: 2010-05-02
"""

# Defines the classification as a simple list of tuples.
_DDC_CLASS_DEFINITION = [
    ('000', 'Computer science, information & general works'),
    ('100', 'Philosophy and psychology'),
    ('200', 'Religion'),
    ('300', 'Social sciences'),
    ('400', 'Language'),
    ('500', 'Science'),
    ('600', 'Technology'),
    ('700', 'Arts and recreation'),
    ('800', 'Literature'),
    ('900', 'History, geography, and biography'),
    ]


# Defines the divisions as a simple list of tuples.
_DDC_DIVISION_DEFINITION = [
    ('000', 'Computer science, knowledge & systems'),
    ('010', 'Bibliographies'),
    ('020', 'Library & information sciences'),
    ('030', 'Encyclopedias & books of facts'),
    ('040', 'Unused'),
    ('050', 'Magazines, journals & serials'),
    ('060', 'Associations, organizations & museums'),
    ('070', 'News media, journalism & publishing'),
    ('080', 'General collections'),
    ('090', 'Manuscripts & rare books'),

    ('100', 'Philosophy & psychology'),
    ('110', 'Metaphysics'),
    ('120', 'Epistemology, causation, humankind'),
    ('130', 'Paranormal phenomena'),
    ('140', 'Specific philosophical schools'),
    ('150', 'Psychology'),
    ('160', 'Logic'),
    ('170', 'Ethics  (Moral philosophy)'),
    ('180', 'Ancient, medieval, Oriental philosophy'),
    ('190', 'Modern Western philosophy'),

    ('200', 'Religion'),
    ('210', 'Natural theology'),
    ('220', 'Bible'),
    ('230', 'Christian theology'),
    ('240', 'Christian moral & devotional theology'),
    ('250', 'Christian orders & local church'),
    ('260', 'Christian social theology'),
    ('270', 'Christian church history'),
    ('280', 'Christian denominations & sects'),
    ('290', 'Other & comparative religions'),

    ('300', 'Social sciences'),
    ('310', 'General statistics'),
    ('320', 'Political science'),
    ('330', 'Economics'),
    ('340', 'Law'),
    ('350', 'Public administration'),
    ('360', 'Social services; association'),
    ('370', 'Education'),
    ('380', 'Commerce, communications, transport'),
    ('390', 'Customs, etiquette, folklore'),

    ('400', 'Language'),
    ('410', 'Linguistics'),
    ('420', 'English & Old English'),
    ('430', 'Germanic languages; German'),
    ('440', 'Romance languages; French'),
    ('450', 'Italian, Romanian, Rhaeto-Romanic'),
    ('460', 'Spanish & Portuguese languages'),
    ('470', 'Italic; Latin'),
    ('480', 'Hellenic languages; Classical Greek'),
    ('490', 'Other languages'),

    ('500', 'Natural sciences & mathematics'),
    ('510', 'Mathematics'),
    ('520', 'Astronomy & allied sciences'),
    ('530', 'Physics'),
    ('540', 'Chemistry & allied sciences'),
    ('550', 'Earth sciences'),
    ('560', 'Paleontology; Paleozoology'),
    ('570', 'Life sciences'),
    ('580', 'Plants'),
    ('590', 'Zoological sciences/Animals'),

    ('600', 'Technology (Applied sciences)'),
    ('610', 'Medical sciences; Medicine'),
    ('620', 'Engineering & Applied operations'),
    ('630', 'Agriculture'),
    ('640', 'Home economics & family living'),
    ('650', 'Management & auxiliary services'),
    ('660', 'Chemical engineering'),
    ('670', 'Manufacturing'),
    ('680', 'Manufacture for specific uses'),
    ('690', 'Buildings'),

    ('700', 'The arts'),
    ('710', 'Civic & landscape art'),
    ('720', 'Architecture'),
    ('730', 'Plastic arts; Sculpture'),
    ('740', 'Drawing & decorative arts'),
    ('750', 'Painting & paintings'),
    ('760', 'Graphic arts; Printmaking & prints'),
    ('770', 'Photography & photographs'),
    ('780', 'Music'),
    ('790', 'Recreational & performing arts'),

    ('800', 'Literature & rhetoric'),
    ('810', 'American literature in English'),
    ('820', 'English & Old English ilteratures'),
    ('830', 'Literatures of Germanic languages'),
    ('840', 'Literatures of Romance languages'),
    ('850', 'Italian, Romanian, Rhaeto-Romanic'),
    ('860', 'Spanish & Portuguese literatures'),
    ('870', 'Italic literatures; Latin'),
    ('880', 'Hellenic literatures; Classical Greek'),
    ('890', 'Literatures of other languages'),

    ('900', 'Geography & history'),
    ('910', 'Geography & travel'),
    ('920', 'Biography, genealogy, Insignia'),
    ('930', 'History of ancient world'),
    ('940', 'General history of Europe'),
    ('950', 'General history of Asia; Far East'),
    ('960', 'General history of Africa'),
    ('970', 'General history of North America'),
    ('980', 'General history of South America'),
    ('990', 'General history of other areas'),

    ]


_MAP_DIVISION_BY_NUMBER = dict([
    (id, (id, desc)) for (id, desc) in _DDC_DIVISION_DEFINITION])

_MAP_DIVISION_BY_DESCRIPTION = dict([
    (desc, (id, desc)) for (id, desc) in _DDC_DIVISION_DEFINITION])


def GetDdcDivisions():
  """Returns the list of all DDC divisions as (id, description) tuples."""
  return _DDC_DIVISION_DEFINITION


def GetDdcDivisionByNumber(id):
  """Gets the (id, description) tuple for the specified DDC id.

  Args:
    id: The three-digit string ID corresponding to a Dewey Decimal Division.

  """
  if isinstance(id, (int, long)):
    id = "%03d" % id
  return _MAP_DIVISION_BY_NUMBER.get(id)


def GetDdcDivisionByDescription(description):
  """Gets the (id, description) tuple for the specified DDC description.

  Args:
    description: The description/name for the Dewey Decimal Division. An
        exact match must be provided.
  """
  return _MAP_DIVISION_BY_DESCRIPTION.get(description)
