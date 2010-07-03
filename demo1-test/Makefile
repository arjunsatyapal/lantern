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

TEST_ARGS = --clear_datastore \
	--datastore_path=$(DATASTORE_DIR)/dev_appserver.datastore

TEST_PORT = 9092

test: $(DATASTORE_DIR) .STALE
	$(APPENGINE_DIR)/$(DEV_SERVER) $(TEST_ARGS) \
         --address $(SERVER_ADDRESS) --port $(TEST_PORT) .

$(DATASTORE_DIR):
	mkdir -p $@

.STALE:
