#!/usr/bin/python2.4
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

# Simple test whether YAML files may be parsed
import sys
import yaml

_USAGE = """testformat file.yaml"""


def _ParseYaml(stream):
  """Parses the file or stream and returns object."""
  return yaml.safe_load(stream)


def _VerityYaml(file_or_stream):
  """Verifies whether specified file is a valid YAML file."""
  if isinstance(file_or_stream, basestring):
    file = open(file_or_stream, "r");
  else:
    file = file_or_stream
  data = _ParseYaml(file)
  print data


def main(argv):
  if len(argv) < 2:
    print _USAGE
    sys.exit(1)
  fname = argv[1]
  _VerityYaml(fname)


if __name__ == '__main__':
  main(sys.argv)
