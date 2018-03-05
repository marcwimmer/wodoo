#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import cherrypy
from subprocess import Popen, PIPE
import hashlib
import subprocess
from json import dumps, loads
from base64 import b64decode, b64encode
import telnetlib
from asterisk.ami import AMIClient, SimpleAction

class ARCLI(object):
    def verify(self, cmd, chash):
        csh_2 = hashlib.sha256(cmd.encode("utf-8")).hexdigest()
        if csh_2 == chash:
            return True
        return False

    @cherrypy.expose
    def d9a1fbfeddcfaf(self, cmd, chash, ttype):
        cmd = b64decode(cmd.strip()).decode("utf-8")
        chash = chash.strip()
        if not self.verify(cmd, chash):
            return {"System-Error": "404"}
        if ttype == "Console":
            cmd = "/usr/sbin/asterisk -x \"{}\"".format(cmd)
            p = subprocess.check_output(cmd, shell=True)
            out = b64encode(p).decode("utf-8")
        elif ttype == "AMI":
            client = AMIClient(address='localhost', port=5038)
            client.login(username='admin', secret='0469fb7914d19888210e54e9fa9c4912')
            params = loads(cmd)
            action = SimpleAction(**params)
            out = client.send_action(action).response
            print(out)
            if not out:
                return dumps({"code": 200, "data": ""})
            out = str(out)
            print(out)

            success = "success" in out
            out = b64encode(out.encode("utf-8")).decode("utf-8")
            if success:
                out = dumps({"code": 418, "exception": "AMI not Successful!", "data": out})
        else:
            raise Exception("Unhandled type")
        return dumps({"code": 200, "data": out})

    @cherrypy.expose
    def index(self):
        return dumps({"Status": "200", "data": "running"})


if __name__ == '__main__':

    @cherrypy.tools.register('before_finalize', priority=60)
    def secureheaders():
        headers = cherrypy.response.headers
        headers['X-Frame-Options'] = 'DENY'
        headers['X-XSS-Protection'] = '1; mode=block'

    conf = {
        "global":
        {
                "server.socket_host": "0.0.0.0",
                "server.socket_port": 7771,
                "server.thread_pool": 8,
                "server.max_request_body_size": 0,
                "server.socket_timeout": 3600,
        },
        "/":
        {
            "tools.sessions.on": True,
            "tools.sessions.secure": True,
            "tools.secureheaders.on": True,
            "tools.encode.on": True,
            "tools.encode.encoding": "utf-8"
        },
    }
    cherrypy.quickstart(ARCLI(), "/", conf)
