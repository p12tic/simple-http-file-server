#!/usr/bin/env python3
''' Copyright (C) 2016-2018  Povilas Kanapickas <povilas@radix.lt>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import os
import shutil
import subprocess
import sys
import time
import unittest
from http import HTTPStatus

import requests


class TestFixture(unittest.TestCase):
    def setUp(self, port=8080, perm_path=None, perms_json=None):
        self.process = None
        self.port = port

        file_dir = os.path.dirname(os.path.abspath(__file__))

        cmd = [sys.executable, os.path.join(file_dir, 'server.py'), str(port)]

        if perms_json is not None:
            perm_path = os.path.join(file_dir, "tmp_tests_perms.json")
            with open(perm_path, "w") as file:
                file.write(perms_json)

        if perm_path is not None:
            perm_path = os.path.abspath(perm_path)
            cmd += ['--access_config', perm_path]

        self.root = os.path.join(file_dir, "tmp_tests_dir")
        if os.path.exists(self.root):
            shutil.rmtree(self.root)
        os.makedirs(self.root)

        self.process = subprocess.Popen(cmd, cwd=self.root)
        time.sleep(1)

    def tearDown(self):
        if self.process is not None:
            self.process.terminate()
            self.process.wait()

    def assert_get(self, path, expected_status, expected_text=None,
                   user=None, psw=None):
        if expected_status != HTTPStatus.OK and expected_text is not None:
            raise Exception('text should not be specified when status is not '
                            'HTTPStatus.OK')

        url = "http://localhost:" + str(self.port) + "/" + path
        if user is not None and psw is not None:
            r = requests.get(url, auth=(user, psw))
        else:
            r = requests.get(url)
        self.assertEqual(expected_status, r.status_code,
                         'Incorrect GET status for url {0}'.format(url))

        if expected_text is not None:
            self.assertEqual(expected_text, r.text,
                             'Incorrect GET text for url {0}'.format(url))

    def assert_put(self, path, expected_status, data, user=None, psw=None):
        url = "http://localhost:" + str(self.port) + "/" + path
        if user is not None and psw is not None:
            r = requests.put(url, data=data, auth=(user, psw))
        else:
            r = requests.put(url, data=data)
        self.assertEqual(expected_status, r.status_code,
                         'Incorrect PUT status for url {0}'.format(url))

    def put_dir(self, path):
        path = os.path.join(self.root, path)
        os.makedirs(path)

    def put_file(self, path, text=None):
        path = os.path.join(self.root, path)
        dir = os.path.dirname(path)
        if not os.path.exists(dir):
            os.makedirs(dir)
        with open(path, "w") as file:
            if text is not None:
                file.write(text)

    def assert_get_path(self, path, text=None):
        path = os.path.join(self.root, path)
        self.assertTrue(os.path.exists(path))

        with open(path, 'r') as file:
            read_text = file.read()
        self.assertEqual(text, read_text,
                         'Incorrect text at path {0}'.format(path))


class TestNoAuth(TestFixture):
    def test_no_auth(self):
        self.assert_get('', HTTPStatus.OK, '{}')
        self.assert_put("ff", HTTPStatus.OK, "1")
        self.assert_get("ff1", HTTPStatus.NOT_FOUND)
        self.assert_get("ff", HTTPStatus.OK, "1")
        self.assert_put("dir/ff", HTTPStatus.OK, "1")
        self.assert_put("dir", HTTPStatus.METHOD_NOT_ALLOWED, "1")
        self.assert_get("dir", HTTPStatus.OK, '{"ff": "file"}')
        self.assert_get("dir/ff", HTTPStatus.OK, "1")
        self.assert_get('', HTTPStatus.OK, '{"dir": "directory", "ff": "file"}')


class TestAuthNoneAllowed(TestFixture):

    def setUp(self):
        perms_json = '''
{
    "paths" : [
        { "path" : ".", "user" : "*", "perms" : "" }
    ],
    "users" : []
}
'''
        super().setUp(perms_json=perms_json)

    def test_none_allowed(self):
        self.assert_get("", HTTPStatus.UNAUTHORIZED)
        self.assert_put("ff", HTTPStatus.UNAUTHORIZED, "1")
        self.assert_get("ff1", HTTPStatus.UNAUTHORIZED)
        self.assert_get("ff", HTTPStatus.UNAUTHORIZED)
        self.assert_put("dir/ff", HTTPStatus.UNAUTHORIZED, "1")
        self.assert_put("dir", HTTPStatus.UNAUTHORIZED, "1")
        self.assert_get("dir", HTTPStatus.UNAUTHORIZED)
        self.assert_get("dir/ff", HTTPStatus.UNAUTHORIZED)


class TestAuthWriteOnly(TestFixture):

    def setUp(self):
        perms_json = '''
{
    "paths" : [
        { "path" : ".", "user" : "*", "perms" : "w" }
    ],
    "users" : []
}
'''
        super().setUp(perms_json=perms_json)

    def test_write_only(self):
        self.assert_get("", HTTPStatus.UNAUTHORIZED)
        self.assert_put("ff", HTTPStatus.OK, "1")
        self.assert_get("ff1", HTTPStatus.UNAUTHORIZED)
        self.assert_get("ff", HTTPStatus.UNAUTHORIZED)
        self.assert_put("dir/ff", HTTPStatus.OK, "1")
        self.assert_get("dir", HTTPStatus.UNAUTHORIZED)
        self.assert_get("dir/ff", HTTPStatus.UNAUTHORIZED)


class TestAuthReadOnly(TestFixture):

    def setUp(self):
        perms_json = '''{
    "paths" : [
        { "path" : ".", "user" : "*", "perms" : "r" }
    ],
    "users" : []
}
'''
        super().setUp(perms_json=perms_json)

    def test_read_only(self):
        self.assert_get("", HTTPStatus.UNAUTHORIZED)
        self.assert_put("ff", HTTPStatus.UNAUTHORIZED, "1")
        self.assert_get("ff1", HTTPStatus.NOT_FOUND)
        self.assert_get("ff", HTTPStatus.NOT_FOUND)
        self.assert_put("dir/ff", HTTPStatus.UNAUTHORIZED, "1")
        self.assert_get("dir", HTTPStatus.NOT_FOUND)
        self.assert_get("dir/ff", HTTPStatus.NOT_FOUND)


class TestAuthListOnly(TestFixture):

    def setUp(self):
        perms_json = '''{
    "paths" : [
        { "path" : ".", "user" : "*", "perms" : "l" }
    ],
    "users" : []
}
'''
        super().setUp(perms_json=perms_json)

    def test_list_only(self):
        self.assert_get("", HTTPStatus.OK, '{}')
        self.assert_put("ff", HTTPStatus.UNAUTHORIZED, '1')
        self.assert_get("ff1", HTTPStatus.UNAUTHORIZED)
        self.assert_get("ff", HTTPStatus.UNAUTHORIZED)
        self.assert_put("dir/ff", HTTPStatus.UNAUTHORIZED, '1')
        self.assert_get("dir", HTTPStatus.UNAUTHORIZED)
        self.assert_get("dir/ff", HTTPStatus.UNAUTHORIZED)

        self.put_dir('dir')
        self.assert_get("", HTTPStatus.OK, '{"dir": "directory"}')
        self.put_file('dir/fn')
        self.assert_get("dir", HTTPStatus.OK, '{"fn": "file"}')
        self.assert_get("dir/fn", HTTPStatus.UNAUTHORIZED)


class TestAuthAllAllowed(TestFixture):

    def setUp(self):
        perms_json = '''
{
    "paths" : [
        { "path" : ".", "user" : "*", "perms" : "rwl" }
    ],
    "users" : []
}
'''
        super().setUp(perms_json=perms_json)

    def test_allowed(self):
        self.assert_get('', HTTPStatus.OK, '{}')
        self.assert_get("ff1", HTTPStatus.NOT_FOUND)
        self.assert_put("ff", HTTPStatus.OK, "1")
        self.assert_get("ff1", HTTPStatus.NOT_FOUND)
        self.assert_get('', HTTPStatus.OK, '{"ff": "file"}')
        self.assert_get("ff", HTTPStatus.OK, "1")
        self.assert_put("dir/ff", HTTPStatus.OK, "1")
        self.assert_get("dir", HTTPStatus.OK, '{"ff": "file"}')
        self.assert_get("dir/ff", HTTPStatus.OK, "1")


class TestComplexPermissions(TestFixture):

    def setUp(self):
        perms_json = '''
{
    "paths" : [
        { "path" : ".", "user" : "*", "perms" : "" },
        { "path" : "or", "user" : "*", "perms" : "r" },
        { "path" : "or", "user" : "user1", "perms" : "w" },
        { "path" : "ow", "user" : "*", "perms" : "w" },
        { "path" : "ow", "user" : "user1", "perms" : "r" },
        { "path" : "ol", "user" : "*", "perms" : "l" },
        { "path" : "ol", "user" : "user1", "perms" : "r" },
        { "path" : "orw", "user" : "*", "perms" : "rw" },
        { "path" : "orw", "user" : "user1", "perms" : "" },
        { "path" : "ur", "user" : "user1", "perms" : "r" },
        { "path" : "uw", "user" : "user1", "perms" : "w" },
        { "path" : "ul", "user" : "user1", "perms" : "l" },
        { "path" : "urw", "user" : "user1", "perms" : "rw" }
    ],
    "users" : [
        { "user" : "user1", "psw" : "pass1" },
        { "user" : "user2", "psw" : "pass2" }
    ]
}
'''
        super().setUp(perms_json=perms_json)

    def test_unauthorized_not_allowed(self):
        self.assert_get("", HTTPStatus.UNAUTHORIZED)
        self.assert_put("ff", HTTPStatus.UNAUTHORIZED, "1")
        self.assert_get("ff1", HTTPStatus.UNAUTHORIZED)

    def test_readonly_unauthorized(self):
        self.assert_get("or", HTTPStatus.NOT_FOUND)
        self.assert_put("or/t", HTTPStatus.OK, "1",
                        user='user1', psw='pass1')
        self.assert_put("or/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user1', psw='p')
        self.assert_put("or/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user2', psw='pass2')
        self.assert_put("or/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user2', psw='p')
        self.assert_get("or/t", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='pass1')
        self.assert_get("or/t", HTTPStatus.OK, "1",
                        user='user2', psw='pass2')
        self.assert_get("or", HTTPStatus.UNAUTHORIZED)
        self.assert_get("or/t", HTTPStatus.OK, "1")

    def test_writeonly_unauthorized(self):
        self.assert_put("ow/t", HTTPStatus.OK, "1")
        self.assert_put("ow/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user1', psw='pass1')
        self.assert_put("ow/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user1', psw='p')
        self.assert_put("ow/t", HTTPStatus.OK, "1",
                        user='user2', psw='pass2')
        self.assert_put("ow/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user2', psw='p')
        self.assert_get("ow", HTTPStatus.UNAUTHORIZED)
        self.assert_get("ow/t", HTTPStatus.UNAUTHORIZED)
        self.assert_get("ow/t", HTTPStatus.OK, "1",
                        user='user1', psw='pass1')
        self.assert_get("ow/t", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='p')
        self.assert_get("ow/t", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='pass2')
        self.assert_get("ow/t", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='p')

    def test_listonly_unauthorized(self):
        self.assert_get('ol', HTTPStatus.UNAUTHORIZED)
        self.assert_get('ol', HTTPStatus.NOT_FOUND,
                        user='user1', psw='pass1')
        self.assert_get('ol', HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='p')
        self.assert_get('ol', HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='pass2')
        self.assert_get('ol', HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='p')
        self.put_dir('ol')
        self.assert_get('ol', HTTPStatus.OK, '{}')
        self.assert_get('ol', HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='pass1')
        self.assert_get('ol', HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='p')
        self.assert_get('ol', HTTPStatus.OK, '{}',
                        user='user2', psw='pass2')
        self.assert_get('ol', HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='p')

        self.assert_put("ol/t", HTTPStatus.UNAUTHORIZED, "1")
        self.assert_put("ol/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user1', psw='pass1')
        self.assert_put("ol/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user1', psw='p')
        self.assert_put("ol/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user2', psw='pass2')
        self.assert_put("ol/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user2', psw='p')

        self.assert_get("ol/t", HTTPStatus.UNAUTHORIZED)
        self.assert_get("ol/t", HTTPStatus.NOT_FOUND,
                        user='user1', psw='pass1')
        self.assert_get("ol/t", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='p')
        self.assert_get("ol/t", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='pass2')
        self.assert_get("ol/t", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='p')

        self.put_file('ol/t', '1')
        self.assert_get("ol/t", HTTPStatus.UNAUTHORIZED)
        self.assert_get("ol/t", HTTPStatus.OK, '1',
                        user='user1', psw='pass1')
        self.assert_get("ol/t", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='p')
        self.assert_get("ol/t", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='pass2')
        self.assert_get("ol/t", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='p')

        self.assert_get('ol', HTTPStatus.OK, '{"t": "file"}')
        self.assert_get('ol', HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='pass1')
        self.assert_get('ol', HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='p')
        self.assert_get('ol', HTTPStatus.OK, '{"t": "file"}',
                        user='user2', psw='pass2')
        self.assert_get('ol', HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='p')

    def test_user_blacklist(self):
        self.assert_get("orw/t", HTTPStatus.NOT_FOUND)
        self.assert_get("orw", HTTPStatus.NOT_FOUND)
        self.assert_put("orw/t", HTTPStatus.OK, "1")
        self.assert_get("orw/t", HTTPStatus.OK, "1")
        self.assert_get("orw", HTTPStatus.UNAUTHORIZED)
        self.assert_put("orw/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user1', psw='pass1')
        self.assert_put("orw/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user1', psw='p')
        self.assert_put("orw/t", HTTPStatus.OK, "1",
                        user='user2', psw='pass2')
        self.assert_put("orw/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user2', psw='p')
        self.assert_get("orw/t", HTTPStatus.OK, "1")
        self.assert_get("orw", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='pass1')
        self.assert_get("orw/t", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='pass1')
        self.assert_get("orw/t", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='p')
        self.assert_get("orw/t", HTTPStatus.OK, "1",
                        user='user2', psw='pass2')
        self.assert_get("orw/t", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='p')

    def test_readonly_user(self):
        self.put_file("ur/t", "1")
        self.assert_get("ur/t", HTTPStatus.UNAUTHORIZED)
        self.assert_get("ur", HTTPStatus.UNAUTHORIZED)
        self.assert_put("ur/t", HTTPStatus.UNAUTHORIZED, "1")
        self.assert_get("ur/t", HTTPStatus.UNAUTHORIZED)

        self.assert_put("ur/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user1', psw='pass1')
        self.assert_put("ur/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user1', psw='p')
        self.assert_put("ur/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user2', psw='pass2')
        self.assert_put("ur/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user2', psw='p')
        self.assert_get("ur/t", HTTPStatus.OK, "1",
                        user='user1', psw='pass1')
        self.assert_get("ur/t", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='pass2')
        self.assert_get("ur", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='pass1')
        self.assert_get("ur", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='p')
        self.assert_get("ur", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='pass2')
        self.assert_get("ur", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='p')

        self.assert_get("ur/t", HTTPStatus.UNAUTHORIZED)
        self.assert_get("ur", HTTPStatus.UNAUTHORIZED)
        self.assert_put("ur/t", HTTPStatus.UNAUTHORIZED, "1")
        self.assert_get("ur/t", HTTPStatus.UNAUTHORIZED)

    def test_writeonly_user(self):
        self.assert_put("uw/t", HTTPStatus.OK, "1",
                        user='user1', psw='pass1')
        self.assert_put("uw/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user1', psw='p')
        self.assert_put("uw/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user2', psw='pass2')
        self.assert_put("uw/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user2', psw='p')
        self.assert_get("uw/t", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='pass1')
        self.assert_get("uw/t", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='pass2')
        self.assert_get("uw", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='pass1')
        self.assert_get("uw", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='p')
        self.assert_get("uw", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='pass2')
        self.assert_get("uw", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='p')
        self.assert_get_path('uw/t', "1")

    def test_listonly_user(self):
        self.put_file("ul/t", "1")
        self.assert_get("ul/t", HTTPStatus.UNAUTHORIZED)
        self.assert_get("ul", HTTPStatus.UNAUTHORIZED)
        self.assert_put("ul/t", HTTPStatus.UNAUTHORIZED, "1")
        self.assert_get("ul/t", HTTPStatus.UNAUTHORIZED)

        self.assert_put("ul/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user1', psw='pass1')
        self.assert_put("ul/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user1', psw='p')
        self.assert_put("ul/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user2', psw='pass2')
        self.assert_put("ul/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user2', psw='p')

        self.assert_get("ul/t", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='pass1')
        self.assert_get("ul/t", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='pass2')
        self.assert_get("ul", HTTPStatus.OK, '{"t": "file"}',
                        user='user1', psw='pass1')
        self.assert_get("ul", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='p')
        self.assert_get("ul", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='pass2')
        self.assert_get("ul", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='p')

    def test_readwrite_user(self):
        self.assert_get("urw/t", HTTPStatus.UNAUTHORIZED)
        self.assert_get("urw", HTTPStatus.UNAUTHORIZED)
        self.assert_put("urw/t", HTTPStatus.UNAUTHORIZED, "1")
        self.assert_get("urw/t", HTTPStatus.UNAUTHORIZED)

        self.assert_put("urw/t", HTTPStatus.OK, "1",
                        user='user1', psw='pass1')
        self.assert_put("urw/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user1', psw='p')
        self.assert_put("urw/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user2', psw='pass2')
        self.assert_put("urw/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user2', psw='p')
        self.assert_get("urw/t", HTTPStatus.OK, "1",
                        user='user1', psw='pass1')
        self.assert_get("urw/t", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='pass2')
        self.assert_get("urw", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='pass1')
        self.assert_get("urw", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='p')
        self.assert_get("urw", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='pass2')
        self.assert_get("urw", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='p')

    def test_nonconfigured_path(self):
        self.assert_put("other/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user1', psw='pass1')
        self.assert_put("other/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user1', psw='p')
        self.assert_put("other/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user2', psw='pass2')
        self.assert_put("other/t", HTTPStatus.UNAUTHORIZED, "1",
                        user='user2', psw='p')
        self.assert_get("other/t", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='pass1')
        self.assert_get("other/t", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='pass2')
        self.assert_get("other", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='pass1')
        self.assert_get("other", HTTPStatus.UNAUTHORIZED,
                        user='user1', psw='p')
        self.assert_get("other", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='pass2')
        self.assert_get("other", HTTPStatus.UNAUTHORIZED,
                        user='user2', psw='p')
