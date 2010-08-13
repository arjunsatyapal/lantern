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

"""URL mappings for the demo package."""

from django.conf.urls import defaults

urlpatterns = defaults.patterns(
    'demo.views',
    (r'^$', 'index'),
    (r'^video$', 'video'),
    (r'^xsrf_token$', 'xsrf_token'),
    (r'^create$', 'create'),
    (r'^view$', 'view_doc'),
    (r'^edit$', 'edit'),
    (r'^list$', 'list_docs'),
    (r'^history$', 'history'),
    (r'^changes$', 'changes'),
    (r'^submitEdits$', 'submit_edits'),
    (r'^temp$', 'temp'),
    # XHR targets

    # Gets session id for a widget
    (r'^getSessionId$', 'get_session_id_for_widget'), 
    # Updates progress score for widget and document for the current user
    # and returns updated accumulated score for the document.
    (r'^updateScore$', 'update_doc_score'),
    (r'^getListAjax$', 'get_list_ajax')
    )
