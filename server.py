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

from http.server import SimpleHTTPRequestHandler, HTTPServer
import argparse
import os
import sys
import base64
import json
import socket

class SimpleUploadHandler(SimpleHTTPRequestHandler):

    def do_PUT(self):
        self.log_headers_if_needed()

        path = self.translate_path(self.path)
        if os.path.isdir(path):
            self.send_error(405)
            return
        try:
            parent_dir = os.path.dirname(path)
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir)

            length = int(self.headers.get('Content-Length'))
            fout = open(path, 'wb')

            while length > 0:
                bufsize = 102400
                if length < bufsize:
                    bufsize = length
                length -= bufsize

                fout.write(self.rfile.read(bufsize))
            fout.close()
        except Exception as e:
            self.log_message("%s", str(e))
            self.send_error(405)
            return

        self.send_response(200)
        self.end_headers()

    def log_write(self, msg):
        if hasattr(self.server, 'log_file') and self.server.log_file is not None:
            self.server.log_file.write(msg)
        else:
            sys.stderr.write(msg)

    def log_headers_if_needed(self):
        if hasattr(self.server, 'log_headers') and self.server.log_headers == True:
            self.log_write(str(self.headers))

    def log_message(self, format, *args):
        msg = "%s - - [%s] %s\n" % (self.address_string(),
                                    self.log_date_time_string(),
                                    format % args)
        self.log_write(msg)

def encode_http_auth_password(user, psw):
    txt = user + ':' + psw
    txt = base64.b64encode(txt.encode('UTF-8')).decode('UTF-8')
    return txt

def decode_http_auth_password(txt):
    txt = base64.b64decode(txt.encode('UTF-8')).decode('UTF-8')
    items = txt.split(':')
    if len(items) != 2:
        return None
    return (items[0], items[1])

class PathConfig:
    def __init__(self, filename):
        if '/' in filename:
            raise Exception()
        self.filename = filename
        self.perms = {}
        self.children = {}

class AuthConfig:

    def __init__(self, log_file=sys.stdout):
        self.root = PathConfig('')
        self.users = {}
        self.log_file = log_file

    def add_path_config(self, path, user, perms):
        path_items = [ p for p in path.split('/') if p not in [ '', '.', '..' ] ]

        p = self.root
        for i in path_items:
            if i not in p.children:
                p.children[i] = PathConfig(i)
            p = p.children[i]

        p.perms[user] = perms

    def load_config(self, config_file_path):
        try:
            config = json.load(open(config_file_path, 'r'))
            config_paths = config['paths']
            for config_path in config_paths:
                path = config_path['path']
                user = config_path['user']
                perms = config_path['perms']
                self.add_path_config(path, user, perms)

            config_users = config['users']
            for config_user in config_users:
                user = config_user['user']
                psw = config_user['psw']
                self.users[user] = psw

        except Exception as e:
            self.log_write("Error reading config file " + config_file_path)
            self.log_write(str(e))

    def check_perm(self, perms, user, perm):
        if user in perms:
            if perm in perms[user]:
                return True
            return False

        if '*' in perms:
            if perm in perms['*']:
                return True
            return False
        return None

    def combine_perm(self, prev, next):
        if next == None:
            return prev
        return next

    def check_path_for_perm(self, path, perm, user, psw):
        if user not in self.users:
            user = '*'
        elif self.users[user] != psw:
            return False

        p = self.root
        items = path.split('/')

        result = self.combine_perm(True, self.check_perm(p.perms, user, perm))

        for i in items:
            if i not in p.children:
                return result
            p = p.children[i]

            result = self.combine_perm(result, self.check_perm(p.perms, user, perm))

        return result

class AuthUploadHandler(SimpleUploadHandler):

    def do_AUTHHEAD(self):
        self.log_headers_if_needed()

        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm=\"Test\"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'Not authenticated\n')

    def check_auth_impl(self, perm):
        try:
            path = self.translate_path(self.path)
            path = os.path.relpath(path)
            if path.startswith('..'):
                return False

            auth_header = self.headers.get('Authorization')
            if auth_header == None:
                (user, psw) = ('*', None)
            else:
                if not auth_header.startswith('Basic '):
                    return False
                decode_result = decode_http_auth_password(auth_header[6:].strip())
                if decode_result == None:
                    return False
                (user, psw) = decode_result
            return self.server.auth_config.check_path_for_perm(path, perm, user, psw)

        except Exception as e:
            self.log_message("%s", str(e))
            self.wfile.write(str(e))
            return False

    def check_auth(self, perm):
        if not self.check_auth_impl(perm):
            self.do_AUTHHEAD()
            return False
        return True

    def do_HEAD(self):
        if self.check_auth('r'):
            self.log_headers_if_needed()
            SimpleHTTPRequestHandler.do_HEAD(self)

    def do_GET(self):
        if self.check_auth('r'):
            self.log_headers_if_needed()
            SimpleHTTPRequestHandler.do_GET(self)

    def do_PUT(self):
        if self.check_auth('w'):
            SimpleUploadHandler.do_PUT(self)

def main():
    parser = argparse.ArgumentParser(prog='server.py')
    parser.add_argument('port', type=int, help="The port to listen on")
    parser.add_argument('--access_config', type=str, default=None,
                        help="Path to access config")
    parser.add_argument('--log_headers', action='store_true', default=False,
                        help="If set logs headers of all requests")
    parser.add_argument('--log', type=str, default=None,
                        help="Path to log file")
    args = parser.parse_args()

    port = args.port
    access_config_path = args.access_config
    log_path = args.log

    if log_path is not None:
        log_file = open(log_path, 'w')
    else:
        log_file = sys.stdout

    if access_config_path is not None and not os.path.exists(access_config_path):
        log_file.write("No such file: " + access_config_path)
        sys.exit(1)

    if access_config_path is None:
        log_file.write('listening on localhost:%d' %(port))
        server = HTTPServer(('localhost', port), SimpleUploadHandler)
    else:
        log_file.write('listening on localhost:%d with access restrictions' %(port))
        auth_config = AuthConfig()
        auth_config.load_config(access_config_path)
        server = HTTPServer(('localhost', port), AuthUploadHandler)
        server.auth_config = auth_config

    server.log_file = log_file
    server.log_headers = args.log_headers
    server.serve_forever()

if __name__ == '__main__':
    main()
