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
    (r'^duplicate$', 'duplicate'),
    (r'^list$', 'list_docs'),
    (r'^history$', 'history'),
    (r'^changes$', 'changes'),
    (r'^submitEdits$', 'submit_edits'),
    (r'^temp$', 'temp'),
    (r'^fetchFromTags$', 'fetch_from_tags'),
    (r'^subjectsDemo$', 'subjectsDemo'),
    (r'^sitemap$', 'sitemap'),

    (r'^admin/upload$', 'upload_file'),

    # XHR targets

    # Gets session id for a widget
    (r'^getSessionId$', 'get_session_id_for_widget'),
    # Gets doc score via ajax
    (r'^getDocScore$', 'get_doc_score'),
    # Updates progress score for widget and document for the current user
    # and returns updated accumulated score for the document.
    (r'^updateScore$', 'update_doc_score'),
    (r'^updateTrunkTitle$', 'update_trunk_title'),
    (r'^getListAjax$', 'get_list_ajax'),
    (r'^newDocumentAjax$', 'new_document_ajax'),
    (r'^markAsReadAjax$', 'mark_as_read'),
    (r'^storeVideoStateAjax$', 'store_video_state'),
    (r'^resetScoreAjax$', 'reset_score_for_page'),
    (r'^subjects/.*$', 'subjectsJson'),
    (r'^notes/update$', 'update_notes'),
    (r'^notes/get$', 'get_notes'),
    (r'^notepad/get$', 'get_notepad'),
    (r'^notepad/update$', 'update_notepad'),
    )
