import cherrypy
from cherrypy.lib.static import serve_file
import json
import os


# Author: Daniel Petermeier
#
# Monjerri is a HTTP Server based on cherrypy,
# to provision SNOM Phones with VPN configurations and 
# configurations.

# Published under IDC License.
# Do what you want with it.

# Usage: python3 monjerri.py

# Requirements: - pip3 install cherrypy
#               - users file containing a nested dictionary in json format: {"username":{"password":"abc1234","archivenr":"50","fts":"test50.tar"}}
# Please be advised, to use Strong Passwords!
# Other authentication methods are not supported by SNOM Phones

# TODO: Implement anti-BruteForce-functionality
# TODO: SSL Implementation possible with SNOM?

class Provisioner(object):
    default = "Welcome to the Provisioner!"
    conf_path = "/root/config/provisioning_users.conf"
    file_path = "/root/transfer"
    users = {}

    def read_conf(self):
        if os.path.exists(self.conf_path):
            with open(self.conf_path, "r") as f:
                self.users = json.loads(f.read())

    @cherrypy.expose
    def index(self):
        return self.default

    @cherrypy.expose
    def provision(self, u=None, p=None, x=None):
        if not (u and p and x):
            return self.default
        self.read_conf()
        try:
            user = self.users[u]
        except KeyError:
            return self.default
        if user["password"] == p and user["archivenr"] == x:
            
            path = os.path.join(self.file_path, user["fts"])
            
            if os.path.exists(path):
                return serve_file(path, "application/x-gtar", "attachment")
            else:
                print("File Path not valid! {}".format(path))
        else:
            print("Params not valid! p={} ({}),  x={} ({})".format(p,user["password"],x,user["archivenr"]))             
        return self.default


if __name__ == '__main__':
    @cherrypy.tools.register('before_finalize', priority=60)
    def secureheaders():
        headers = cherrypy.response.headers
        headers['X-Frame-Options'] = 'DENY'
        headers['X-XSS-Protection'] = '1; mode=block'


    conf = {
        "global":
            {
		"server.socket_host":"0.0.0.0",
                "server.socket_port": 8080,
                "tools.staticdir.on": True,
                "tools.staticdir.dir": "/root/transfer",
            },
        "/": {
            "tools.sessions.on": True,
            "tools.sessions.secure": True,
            "tools.secureheaders.on": True,
            "tools.encode.on": True,
            "tools.encode.encoding": "utf-8"
        },
    }
    cherrypy.quickstart(Provisioner(), "/", conf)
