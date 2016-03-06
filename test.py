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

class Test:
    def __init__(self, port = 8080, perm_path = None, perms_json = None):
        self.process = None
        self.port = port

        file_dir = os.path.dirname(os.path.abspath(__file__))

        cmd = ["python3", os.path.join(file_dir, 'server.py'), str(port)]

        if perms_json != None:
            perm_path = os.path.join(file_dir, "tmp_tests_perms.json")
            open(perm_path, "w").write(perms_json)

        if perm_path != None:
            perm_path = os.path.abspath(perm_path)
            cmd += ['--access_config', perm_path]

        self.root = os.path.join(file_dir, "tmp_tests_dir")
        if os.path.exists(self.root):
            shutil.rmtree(self.root)
        os.makedirs(self.root)

        self.process = subprocess.Popen(cmd, cwd=self.root)
        time.sleep(1)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.process != None:
            self.process.terminate()
            self.process.wait()

    def test_get(self, path, expected_status, expected_text=None, user=None, psw=None):
        url = "http://localhost:" + str(self.port) + "/" + path
        if user != None and psw != None:
            r = requests.get(url, auth=(user, psw))
        else:
            r = requests.get(url)
        if r.status_code != expected_status:
            raise Exception("Unexpected status code: " +
                            "expected:{0} got:{1}".format(expected_status, r.status_code))
        if expected_text != None and r.text != expected_text:
            raise Exception("Unexpected text: " +
                            "expected:{0} got:{1}".format(expected_text, r.text))

    def test_put(self, path, expected_status, data, user=None, psw=None):
        url = "http://localhost:" + str(self.port) + "/" + path
        if user != None and psw != None:
            r = requests.put(url, data=data, auth=(user, psw))
        else:
            r = requests.put(url, data=data)
        if r.status_code != expected_status:
            raise Exception("Unexpected status code: " +
                            "expected:{0} got:{1}".format(expected_status, r.status_code))

    def put_path(self, path, text=None):
        path = os.path.join(self.root, path)
        dir = os.path.dirname(path)
        if not os.path.exists(dir):
            os.makedirs(dir)
        if text == None:
            open(path, "w")
        else:
            open(path, "w").write(text)

    def test_get_path(self, path, text=None):
        path = os.path.join(self.root, path)
        if not os.path.exists(path):
            raise Exception("File does not exist {0}".format(path))
        read_text = open(path, 'r').read()
        if text != None and text != read_text:
            raise Exception("Unexpected text at path {0}: " +
                            "expected:{1} got:{2}".format(path, text, read_text))

with Test() as test:
    test.test_get("", 200)
    test.test_put("ff", 200, "1")
    test.test_get("ff1", 404)
    test.test_get("ff", 200, "1")
    test.test_put("dir/ff", 200, "1")
    test.test_put("dir", 405, "1")
    test.test_get("dir", 200)
    test.test_get("dir/ff", 200, "1")

perms_json = '''
{
    "paths" : [
        { "path" : ".", "user" : "*", "perms" : "" }
    ],
    "users" : []
}
'''

# No requests should be allowed
with Test(perms_json=perms_json) as test:
    test.test_get("", 401)
    test.test_put("ff", 401, "1")
    test.test_get("ff1", 401)
    test.test_get("ff", 401)
    test.test_put("dir/ff", 401, "1")
    test.test_put("dir", 401, "1")
    test.test_get("dir", 401)
    test.test_get("dir/ff", 401)

perms_json = '''
{
    "paths" : [
        { "path" : ".", "user" : "*", "perms" : "w" }
    ],
    "users" : []
}
'''

# Should allow only write requests
with Test(perms_json=perms_json) as test:
    test.test_get("", 401)
    test.test_put("ff", 200, "1")
    test.test_get("ff1", 401)
    test.test_get("ff", 401)
    test.test_put("dir/ff", 200, "1")
    test.test_get("dir", 401)
    test.test_get("dir/ff", 401)

perms_json = '''
{
    "paths" : [
        { "path" : ".", "user" : "*", "perms" : "r" }
    ],
    "users" : []
}
'''

# Should allow only read requests
with Test(perms_json=perms_json) as test:
    test.test_get("", 200)
    test.test_put("ff", 401, "1")
    test.test_get("ff1", 404)
    test.test_get("ff", 404)
    test.test_put("dir/ff", 401, "1")
    test.test_get("dir", 404)
    test.test_get("dir/ff", 404)

perms_json = '''
{
    "paths" : [
        { "path" : ".", "user" : "*", "perms" : "rw" }
    ],
    "users" : []
}
'''

# Should allow all requests
with Test(perms_json=perms_json) as test:
    test.test_get("", 200)
    test.test_get("ff1", 404)
    test.test_put("ff", 200, "1")
    test.test_get("ff1", 404)
    test.test_get("ff", 200, "1")
    test.test_put("dir/ff", 200, "1")
    test.test_get("dir", 200)
    test.test_get("dir/ff", 200, "1")

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

with Test(perms_json=perms_json) as test:
    test.test_get("", 401)
    test.test_put("ff", 401, "1")
    test.test_get("ff1", 401)

    test.test_get("or", 404)
    test.test_put("or/t", 200, "1", user='user1', psw='pass1')
    test.test_put("or/t", 401, "1", user='user1', psw='p')
    test.test_put("or/t", 401, "1", user='user2', psw='pass2')
    test.test_put("or/t", 401, "1", user='user2', psw='p')
    test.test_get("or/t", 401, user='user1', psw='pass1')
    test.test_get("or/t", 200, "1", user='user2', psw='pass2')
    test.test_get("or", 200)
    test.test_get("or/t", 200, "1")

    test.test_put("ow/t", 200, "1")
    test.test_put("ow/t", 401, "1", user='user1', psw='pass1')
    test.test_put("ow/t", 401, "1", user='user1', psw='p')
    test.test_put("ow/t", 200, "1", user='user2', psw='pass2')
    test.test_put("ow/t", 401, "1", user='user2', psw='p')
    test.test_get("ow", 401)
    test.test_get("ow/t", 401)
    test.test_get("ow/t", 200, "1", user='user1', psw='pass1')
    test.test_get("ow/t", 401, user='user1', psw='p')
    test.test_get("ow/t", 401, user='user2', psw='pass2')
    test.test_get("ow/t", 401, user='user2', psw='p')

    test.test_get("orw/t", 404)
    test.test_get("orw", 404)
    test.test_put("orw/t", 200, "1")
    test.test_get("orw/t", 200, "1")
    test.test_get("orw", 200)
    test.test_put("orw/t", 401, "1", user='user1', psw='pass1')
    test.test_put("orw/t", 401, "1", user='user1', psw='p')
    test.test_put("orw/t", 200, "1", user='user2', psw='pass2')
    test.test_put("orw/t", 401, "1", user='user2', psw='p')
    test.test_get("orw/t", 200, "1")
    test.test_get("orw", 401, user='user1', psw='pass1')
    test.test_get("orw/t", 401, user='user1', psw='pass1')
    test.test_get("orw/t", 401, user='user1', psw='p')
    test.test_get("orw/t", 200, "1", user='user2', psw='pass2')
    test.test_get("orw/t", 401, user='user2', psw='p')

    test.put_path("ur/t", "1")
    test.test_get("ur/t", 401)
    test.test_get("ur", 401)
    test.test_put("ur/t", 401, "1")
    test.test_get("ur/t", 401)

    test.test_put("ur/t", 401, "1", user='user1', psw='pass1')
    test.test_put("ur/t", 401, "1", user='user1', psw='p')
    test.test_put("ur/t", 401, "1", user='user2', psw='pass2')
    test.test_put("ur/t", 401, "1", user='user2', psw='p')
    test.test_get("ur/t", 200, "1", user='user1', psw='pass1')
    test.test_get("ur/t", 401, user='user2', psw='pass2')
    test.test_get("ur", 200, user='user1', psw='pass1')
    test.test_get("ur", 401, user='user1', psw='p')
    test.test_get("ur", 401, user='user2', psw='pass2')
    test.test_get("ur", 401, user='user2', psw='p')

    test.test_get("ur/t", 401)
    test.test_get("ur", 401)
    test.test_put("ur/t", 401, "1")
    test.test_get("ur/t", 401)

    test.test_put("uw/t", 200, "1", user='user1', psw='pass1')
    test.test_put("uw/t", 401, "1", user='user1', psw='p')
    test.test_put("uw/t", 401, "1", user='user2', psw='pass2')
    test.test_put("uw/t", 401, "1", user='user2', psw='p')
    test.test_get("uw/t", 401, user='user1', psw='pass1')
    test.test_get("uw/t", 401, user='user2', psw='pass2')
    test.test_get("uw", 401, user='user1', psw='pass1')
    test.test_get("uw", 401, user='user1', psw='p')
    test.test_get("uw", 401, user='user2', psw='pass2')
    test.test_get("uw", 401, user='user2', psw='p')
    test.test_get_path('uw/t', "1")

    test.test_get("urw/t", 401)
    test.test_get("urw", 401)
    test.test_put("urw/t", 401, "1")
    test.test_get("urw/t", 401)

    test.test_put("urw/t", 200, "1", user='user1', psw='pass1')
    test.test_put("urw/t", 401, "1", user='user1', psw='p')
    test.test_put("urw/t", 401, "1", user='user2', psw='pass2')
    test.test_put("urw/t", 401, "1", user='user2', psw='p')
    test.test_get("urw/t", 200, "1", user='user1', psw='pass1')
    test.test_get("urw/t", 401, user='user2', psw='pass2')
    test.test_get("urw", 200, user='user1', psw='pass1')
    test.test_get("urw", 401, user='user1', psw='p')
    test.test_get("urw", 401, user='user2', psw='pass2')
    test.test_get("urw", 401, user='user2', psw='p')

    test.test_put("other/t", 401, "1", user='user1', psw='pass1')
    test.test_put("other/t", 401, "1", user='user1', psw='p')
    test.test_put("other/t", 401, "1", user='user2', psw='pass2')
    test.test_put("other/t", 401, "1", user='user2', psw='p')
    test.test_get("other/t", 401, user='user1', psw='pass1')
    test.test_get("other/t", 401, user='user2', psw='pass2')
    test.test_get("other", 401, user='user1', psw='pass1')
    test.test_get("other", 401, user='user1', psw='p')
    test.test_get("other", 401, user='user2', psw='pass2')
    test.test_get("other", 401, user='user2', psw='p')





