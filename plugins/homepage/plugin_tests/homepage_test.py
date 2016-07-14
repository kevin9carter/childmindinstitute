#!/usr/bin/env python
# -*- coding: utf-8 -*-

###############################################################################
#  Copyright 2016 Kitware Inc.
#
#  Licensed under the Apache License, Version 2.0 ( the "License" );
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
###############################################################################

from tests import base


def setUpModule():
    base.enabledPlugins.append('homepage')
    base.startServer()


def tearDownModule():
    base.stopServer()


class HomepageTest(base.TestCase):

    def testGetMarkdown(self):
        key = 'homepage.markdown'

        # test without set
        resp = self.request('/homepage/markdown')
        self.assertStatusOk(resp)
        self.assertIs(resp.json[key], None)

        # set markdown
        self.model('setting').set(key, 'foo')

        # verify we can get the markdown without being authenticated
        resp = self.request('/homepage/markdown')
        self.assertStatusOk(resp)
        self.assertEquals(resp.json[key], 'foo')
