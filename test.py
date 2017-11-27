#!/usr/bin/env python3
''' Copyright (C) 2016  Povilas Kanapickas <povilas@radix.lt>

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
import requests
import time
import unittest

class TestFixture(unittest.TestCase):
    def setUp(self, port = 8080, perm_path = None, perms_json = None):
        self.process = None
        self.port = port

        file_dir = os.path.dirname(os.path.abspath(__file__))

        cmd = ["python3", os.path.join(file_dir, 'server.py'), str(port)]

        if perms_json != None:
            perm_path = os.path.join(file_dir, "tmp_tests_perms.json")
            with open(perm_path, "w") as file:
                file.write(perms_json)

        if perm_path != None:
            perm_path = os.path.abspath(perm_path)
            cmd += ['--access_config', perm_path]

        self.root = os.path.join(file_dir, "tmp_tests_dir")
        if os.path.exists(self.root):
            shutil.rmtree(self.root)
        os.makedirs(self.root)

        self.process = subprocess.Popen(cmd, cwd=self.root)
        time.sleep(1)

    def tearDown(self):
        if self.process != None:
            self.process.terminate()
            self.process.wait()

    def assert_get(self, path, expected_status, expected_text=None, user=None, psw=None):
        url = "http://localhost:" + str(self.port) + "/" + path
        if user != None and psw != None:
            r = requests.get(url, auth=(user, psw))
        else:
            r = requests.get(url)
        self.assertEqual(expected_status, r.status_code,
                         'Incorrect GET status for url {0}'.format(url))
        if expected_text != None:
            self.assertEqual(expected_text, r.text,
                             'Incorrect GET text for url {0}'.format(url))

    def assert_put(self, path, expected_status, data, user=None, psw=None):
        url = "http://localhost:" + str(self.port) + "/" + path
        if user != None and psw != None:
            r = requests.put(url, data=data, auth=(user, psw))
        else:
            r = requests.put(url, data=data)
        self.assertEqual(expected_status, r.status_code,
                         'Incorrect PUT status for url {0}'.format(url))

    def put_path(self, path, text=None):
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
        self.assert_get("", 200)
        self.assert_put("ff", 200, "1")
        self.assert_get("ff1", 404)
        self.assert_get("ff", 200, "1")
        self.assert_put("dir/ff", 200, "1")
        self.assert_put("dir", 405, "1")
        self.assert_get("dir", 200)
        self.assert_get("dir/ff", 200, "1")

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
        self.assert_get("", 401)
        self.assert_put("ff", 401, "1")
        self.assert_get("ff1", 401)
        self.assert_get("ff", 401)
        self.assert_put("dir/ff", 401, "1")
        self.assert_put("dir", 401, "1")
        self.assert_get("dir", 401)
        self.assert_get("dir/ff", 401)

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
        self.assert_get("", 401)
        self.assert_put("ff", 200, "1")
        self.assert_get("ff1", 401)
        self.assert_get("ff", 401)
        self.assert_put("dir/ff", 200, "1")
        self.assert_get("dir", 401)
        self.assert_get("dir/ff", 401)

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
        self.assert_get("", 200)
        self.assert_put("ff", 401, "1")
        self.assert_get("ff1", 404)
        self.assert_get("ff", 404)
        self.assert_put("dir/ff", 401, "1")
        self.assert_get("dir", 404)
        self.assert_get("dir/ff", 404)

class TestAuthAllAllowed(TestFixture):

    def setUp(self):
        perms_json = '''
{
    "paths" : [
        { "path" : ".", "user" : "*", "perms" : "rw" }
    ],
    "users" : []
}
'''
        super().setUp(perms_json=perms_json)

    def test_allowed(self):
        self.assert_get("", 200)
        self.assert_get("ff1", 404)
        self.assert_put("ff", 200, "1")
        self.assert_get("ff1", 404)
        self.assert_get("ff", 200, "1")
        self.assert_put("dir/ff", 200, "1")
        self.assert_get("dir", 200)
        self.assert_get("dir/ff", 200, "1")

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
        { "path" : "orw", "user" : "*", "perms" : "rw" },
        { "path" : "orw", "user" : "user1", "perms" : "" },
        { "path" : "ur", "user" : "user1", "perms" : "r" },
        { "path" : "uw", "user" : "user1", "perms" : "w" },
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
        self.assert_get("", 401)
        self.assert_put("ff", 401, "1")
        self.assert_get("ff1", 401)

    def test_readonly_unauthorized(self):
        self.assert_get("or", 404)
        self.assert_put("or/t", 200, "1", user='user1', psw='pass1')
        self.assert_put("or/t", 401, "1", user='user1', psw='p')
        self.assert_put("or/t", 401, "1", user='user2', psw='pass2')
        self.assert_put("or/t", 401, "1", user='user2', psw='p')
        self.assert_get("or/t", 401, user='user1', psw='pass1')
        self.assert_get("or/t", 200, "1", user='user2', psw='pass2')
        self.assert_get("or", 200)
        self.assert_get("or/t", 200, "1")

    def test_writeonly_unauthorized(self):
        self.assert_put("ow/t", 200, "1")
        self.assert_put("ow/t", 401, "1", user='user1', psw='pass1')
        self.assert_put("ow/t", 401, "1", user='user1', psw='p')
        self.assert_put("ow/t", 200, "1", user='user2', psw='pass2')
        self.assert_put("ow/t", 401, "1", user='user2', psw='p')
        self.assert_get("ow", 401)
        self.assert_get("ow/t", 401)
        self.assert_get("ow/t", 200, "1", user='user1', psw='pass1')
        self.assert_get("ow/t", 401, user='user1', psw='p')
        self.assert_get("ow/t", 401, user='user2', psw='pass2')
        self.assert_get("ow/t", 401, user='user2', psw='p')

    def test_user_blacklist(self):
        self.assert_get("orw/t", 404)
        self.assert_get("orw", 404)
        self.assert_put("orw/t", 200, "1")
        self.assert_get("orw/t", 200, "1")
        self.assert_get("orw", 200)
        self.assert_put("orw/t", 401, "1", user='user1', psw='pass1')
        self.assert_put("orw/t", 401, "1", user='user1', psw='p')
        self.assert_put("orw/t", 200, "1", user='user2', psw='pass2')
        self.assert_put("orw/t", 401, "1", user='user2', psw='p')
        self.assert_get("orw/t", 200, "1")
        self.assert_get("orw", 401, user='user1', psw='pass1')
        self.assert_get("orw/t", 401, user='user1', psw='pass1')
        self.assert_get("orw/t", 401, user='user1', psw='p')
        self.assert_get("orw/t", 200, "1", user='user2', psw='pass2')
        self.assert_get("orw/t", 401, user='user2', psw='p')

    def test_readonly_user(self):
        self.put_path("ur/t", "1")
        self.assert_get("ur/t", 401)
        self.assert_get("ur", 401)
        self.assert_put("ur/t", 401, "1")
        self.assert_get("ur/t", 401)

        self.assert_put("ur/t", 401, "1", user='user1', psw='pass1')
        self.assert_put("ur/t", 401, "1", user='user1', psw='p')
        self.assert_put("ur/t", 401, "1", user='user2', psw='pass2')
        self.assert_put("ur/t", 401, "1", user='user2', psw='p')
        self.assert_get("ur/t", 200, "1", user='user1', psw='pass1')
        self.assert_get("ur/t", 401, user='user2', psw='pass2')
        self.assert_get("ur", 200, user='user1', psw='pass1')
        self.assert_get("ur", 401, user='user1', psw='p')
        self.assert_get("ur", 401, user='user2', psw='pass2')
        self.assert_get("ur", 401, user='user2', psw='p')

        self.assert_get("ur/t", 401)
        self.assert_get("ur", 401)
        self.assert_put("ur/t", 401, "1")
        self.assert_get("ur/t", 401)

    def test_writeonly_user(self):
        self.assert_put("uw/t", 200, "1", user='user1', psw='pass1')
        self.assert_put("uw/t", 401, "1", user='user1', psw='p')
        self.assert_put("uw/t", 401, "1", user='user2', psw='pass2')
        self.assert_put("uw/t", 401, "1", user='user2', psw='p')
        self.assert_get("uw/t", 401, user='user1', psw='pass1')
        self.assert_get("uw/t", 401, user='user2', psw='pass2')
        self.assert_get("uw", 401, user='user1', psw='pass1')
        self.assert_get("uw", 401, user='user1', psw='p')
        self.assert_get("uw", 401, user='user2', psw='pass2')
        self.assert_get("uw", 401, user='user2', psw='p')
        self.assert_get_path('uw/t', "1")

    def test_readwrite_user(self):
        self.assert_get("urw/t", 401)
        self.assert_get("urw", 401)
        self.assert_put("urw/t", 401, "1")
        self.assert_get("urw/t", 401)

        self.assert_put("urw/t", 200, "1", user='user1', psw='pass1')
        self.assert_put("urw/t", 401, "1", user='user1', psw='p')
        self.assert_put("urw/t", 401, "1", user='user2', psw='pass2')
        self.assert_put("urw/t", 401, "1", user='user2', psw='p')
        self.assert_get("urw/t", 200, "1", user='user1', psw='pass1')
        self.assert_get("urw/t", 401, user='user2', psw='pass2')
        self.assert_get("urw", 200, user='user1', psw='pass1')
        self.assert_get("urw", 401, user='user1', psw='p')
        self.assert_get("urw", 401, user='user2', psw='pass2')
        self.assert_get("urw", 401, user='user2', psw='p')

    def test_nonconfigured_path(self):
        self.assert_put("other/t", 401, "1", user='user1', psw='pass1')
        self.assert_put("other/t", 401, "1", user='user1', psw='p')
        self.assert_put("other/t", 401, "1", user='user2', psw='pass2')
        self.assert_put("other/t", 401, "1", user='user2', psw='p')
        self.assert_get("other/t", 401, user='user1', psw='pass1')
        self.assert_get("other/t", 401, user='user2', psw='pass2')
        self.assert_get("other", 401, user='user1', psw='pass1')
        self.assert_get("other", 401, user='user1', psw='p')
        self.assert_get("other", 401, user='user2', psw='pass2')
        self.assert_get("other", 401, user='user2', psw='p')
