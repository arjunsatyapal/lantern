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

"""Django Forms."""

# Django imports
from django import forms


class UploadFileForm(forms.Form):
  """Defines a simple form for uploading a file."""

  # tuples are (selection_id, title)
  content_type = forms.ChoiceField(choices=[
      ('khan_math_videos', 'Khan Math Videos'),
      ])
  file = forms.FileField()
  start_index = forms.IntegerField(required=False)
  batch_size = forms.IntegerField(required=False)
