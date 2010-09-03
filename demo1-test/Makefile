# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Usage:
#
#  To start the test server:
#    make test

# ASSUMPTION: .google_appenine is a symbolic link to the SDK. May be replaced
# with absolute path.
APPENGINE_DIR = .google_appengine

# Address for the server name. Defaults to localhost
SERVER_ADDRESS = $(shell hostname -f)

DEV_SERVER = dev_appserver.py
APP_CFG = appcfg.py
DATASTORE_DIR = /tmp/$(shell basename $(shell pwd))

TEST_ARGS = \
    --datastore_path=$(DATASTORE_DIR)/dev_appserver.datastore

TEST_PORT = 9094

# ASSUMPTION: .closure_compiler is symbolic link to the compiler dir.
CLOSURE_COMPILER_DIR = .closure_compiler
CLOSURE_COMPILER = $(CLOSURE_COMPILER_DIR)/compiler.jar
CLOSURE_COMPILER_OPTS = # -f --compilation_level=ADVANCED_OPTIMIZATIONS

# Closure javascript location
CLOSURE_JS_DIR = static/js/closure-library-read-only
CLOSURE_DEPS = $(CLOSURE_JS_DIR)/closure/bin/calcdeps.py

# JavaScript files
LANTERN_JS_FILE = static/js/lanternJs.js
LANTERN_JS_BUNDLE_FILE = static/js/lanternJs-bundle.js

JS_SRCS = \
    providerxhr.js \
    subject.js \
    subjectmenu.js \
    subjectxhr.js \
    mocksubjects.js \
    subjectmenu.js \
    lantern_comm.js \
    lantern_quiz.js \
    lantern_widget_channel.js \
    notes.js

JS_FILES = $(patsubst %,static/js/%,$(JS_SRCS))

# -------
# Rules
# -------

test: $(DATASTORE_DIR) .STALE
	$(APPENGINE_DIR)/$(DEV_SERVER) $(TEST_ARGS) \
         --address $(SERVER_ADDRESS) --port $(TEST_PORT) .

$(DATASTORE_DIR):
	mkdir -p $@

# Compiled single-file js
$(LANTERN_JS_FILE): $(JS_FILES)
	$(CLOSURE_DEPS) $(patsubst %,--input=%, $^) -p $(CLOSURE_JS_DIR) \
	  -c $(CLOSURE_COMPILER) $(CLOSURE_COMPILER_OPTS) -o compiled > $@

# Non-compiled single-file js
$(LANTERN_JS_BUNDLE_FILE): $(JS_FILES)
	$(CLOSURE_DEPS) $(patsubst %,--input=%, $^) -p $(CLOSURE_JS_DIR) \
	   -o script > $@

deploy_js: $(LANTERN_JS_FILE) $(LANTERN_JS_BUNDLE_FILE)

.STALE:
