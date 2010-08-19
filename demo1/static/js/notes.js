// Copyright 2010 Google Inc.
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

goog.require('goog.ui.Popup');
goog.require('goog.net.XhrIo');
goog.require('goog.Uri');
goog.require('goog.json');
goog.provide('lantern.Notes');

lantern.Notes.showNote = function(name) {
  var noteElt = document.getElementById(name);
  var note = new goog.ui.Popup(noteElt);

  note.onHide_ = function(opt_target) {
    var contents = noteElt.value;
    var uri = new goog.Uri('/notes/update');
    var data = goog.json.serialize({ 'name': name, 'data': contents });
    // alert("Sending " + data);

    goog.net.XhrIo.send(uri, function(e) {
        var xhr = e.target;
        var obj = xhr.getResponseText();
        // alert("Done " + obj);
      }, "POST", "data=" + data);

    goog.ui.PopupBase.prototype.onHide_.call(note);
  };
  note.setVisible(true);
}
