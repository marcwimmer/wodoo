# -*- coding: utf-8 -*-
import uuid
import json
import requests
import os
import socket
import ari
import cherrypy as cp
import threading
import inspect
import pymustache
import xmlrpclib
import time
import subprocess
import traceback
import sys
import logging
import hashlib
import base64
import websocket
from threading import Lock, Thread
dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))) # script directory

OUTSIDE_PORT = os.environ['OUTSIDE_PORT']
APP_NAME = 'odoo-asterisk-connector'

data = {
    'client': None,
}

odoo = {
    'host': "http://{}:{}".format(os.environ['ODOO_HOST'], os.environ['ODOO_PORT']),
    'username': os.environ['PHONEBOX_ODOO_USER'],
    'pwd': os.environ['PHONEBOX_ODOO_PASSWORD'],
    'db': os.environ['DBNAME'],
}

FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
logging.basicConfig(format=FORMAT)
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger('')  # root handler

class Connector(object):

    def __init__(self):
        self.lock = Lock()
        self.blocked_extensions = set()
        self.extensions = {}

        self.client().applications.subscribe(applicationName=[APP_NAME], eventSource="endpoint:SIP")
        # self.client.applications.subscribe(applicationName=[APP_NAME], eventSource="endpoint:PJSIP")
        self.client().on_channel_event("ChannelCreated", self.onChannelStateChanged)
        self.client().on_channel_event("ChannelStateChange", self.onChannelStateChanged)
        self.client().on_channel_event("ChannelDestroyed", self.onChannelDestroyed)

    def client(self):
        return data['client']

    class ExtensionState(object):
        def __init__(self, parent, extension):
            self.parent = parent
            self.extension = extension
            self.state = "Down"

        def reset(self):
            self.update_state("Down")

        def update_state(self, state, channel=False, bridge=False):
            changed = False
            if self.state != state:
                changed = True
            if changed:
                self.state = state

            other_channels = []
            # try to identify session for attended transfers
            if state == "Ringing":
                if channel:
                    number = channel['connected']['number']
                    all_channels = map(lambda c: c.json, self.parent.client().channels.list())
                    other_channels = filter(lambda c: c.get('caller', {}).get('number', False) == number or c.get('connected', {}).get('number', False) == number, all_channels)
                    other_channels = filter(lambda c: c['id'] != channel['id'], all_channels)

            if changed:
                self.parent.odoo('asterisk.connector', 'asterisk_updated_channel_state', self.extension, self.state, channel, other_channels)

        def jsonify(self):
            return {
                'state': self.state or 'Down',
                'extension': self.extension,
            }

    def on_channel_change(self, channel_json):
        with self.lock:
            if channel_json.get('caller', False):
                if channel_json['caller'].get('number', False):
                    extension = channel_json['caller']['number'] # e.g. 80
                    self.extensions.setdefault(extension, Connector.ExtensionState(self, extension))
                    bridges = map(lambda bridge: bridge.json, filter(lambda bridge: channel_json['id'] in bridge.json['channels'], self.client().bridges.list()))
                    self.extensions[extension].update_state(state=channel_json['state'], channel=channel_json, bridge=bridges[0] if bridges else False)

    def onChannelDestroyed(self, channel_obj, ev):
        channel = channel_obj.json
        channel['state'] = "Down"
        self.on_channel_change(channel)

    def onChannelStateChanged(self, channel_obj, ev):
        self.on_channel_change(channel_obj.json)

    def odoo(self, *params):
        def login(username, password):
            socket_obj = xmlrpclib.ServerProxy('%s/xmlrpc/common' % (odoo['host']))
            uid = socket_obj.login(odoo['db'], username, password)
            return uid
        uid = login(odoo['username'], odoo['pwd'])

        socket_obj = xmlrpclib.ServerProxy('%s/xmlrpc/object' % (odoo['host']))
        return socket_obj.execute(odoo['db'], uid, odoo['pwd'], *params)

    @cp.expose
    def index(self):
        with open(os.path.join(dir, 'templates/index.html')) as f:
            content = f.read()
        content = pymustache.render(content, {
            'base_url': 'http://localhost:{port}'.format(port=OUTSIDE_PORT),
        })
        return content

    @cp.expose
    def simulate_set_blocked(self, extension, blocked):
        extension = long(extension)
        blocked = long(blocked) == 1
        with self.lock:
            if blocked:
                self.blocked_extensions.add(extension)
            else:
                self.blocked_extensions.remove(extension)
        self.odoo('asterisk.connector', 'asterisk_updated_block_state', extension, blocked)

    @cp.tools.json_in()
    @cp.tools.json_out()
    @cp.expose
    def get_active_channel(self):
        number = cp.request.json['number']
        channels = map(lambda c: c.json, self.client().channels.list())
        channels = filter(lambda c: str(c.get('caller', {}).get('number', False)) == str(number), channels)
        if channels:
            return channels[0]['id']

    @cp.tools.json_in()
    @cp.tools.json_out()
    @cp.expose
    def attended_transfer(self):
        # https://wiki.asterisk.org/wiki/display/AST/Asterisk+13+ManagerAction_Atxfer
        action = {
            "name": 'Atxfer',
            "ActionID": str(uuid.uuid4()),
            "Channel": cp.request.json['channel_id'],
            "Exten": cp.request.json['exten'],
            "Context": cp.request.json['context'],
        }
        self.adminconsole(action, 'AMI')

    def adminconsole(self, cmd, ttype):
        """
        :param ttype: values: 'AMI', 'Console'

        """
        assert ttype in ['AMI', 'Console']
        if ttype == "AMI":
            assert isinstance(cmd, dict)
            cmd = json.dumps(cmd)

        h = hashlib.sha256()
        h.update(cmd)
        hash = h.hexdigest()
        cmd = base64.b64encode(cmd)

        url = "http://{server}:{port}/d9a1fbfeddcfaf?cmd={cmd}&ttype={type}&chash={hash}".format(
            server=os.environ['ASTERISK_SERVER'],
            port=os.environ['ASTERISK_CUSTOM_ADMIN_PORT'],
            cmd=cmd,
            hash=hash,
            type=ttype,
        )
        r = requests.get(url)
        if r.status_code != 200:
            r.raise_for_status()
        result = base64.b64decode(r.json()['data'])
        return result

    @cp.tools.json_in()
    @cp.tools.json_out()
    @cp.expose
    def set_dnd(self):
        self.adminconsole("database {verb} DND {endpoint} {dnd}".format(
            endpoint=cp.request.json['endpoint'],
            dnd='YES' if cp.request.json['dnd'] else '',
            verb='put' if cp.request.json['dnd'] else 'del',
        ), 'Console')

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def dnd(self):
        dnds = self.adminconsole("database show dnd", 'Console')
        result = []
        for line in dnds.split("\n"):
            line = line.strip()
            if line.startswith("/DND/"):
                extension = long(line.split("/DND/")[-1].split(":")[0].strip())
                result.append(extension)
        return result

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def get_state(self):

        # http://18.196.22.95:7771/d9a1fbfeddcfaf?cmd="test"&hash=
        r = self.adminconsole("sip show channels", "Console")
        dnds = self.dnd()

        return {
            'admin': r,
            'channels': [x.json for x in self.client().channels.list()],
            'dnds': dnds,
        }

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def get_extension_states(self):
        return [x.jsonify() for x in self.extensions.values()]

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def get_blocked_extensions(self):
        with self.lock:
            return {
                'blocked': list(self.blocked_extensions),
            }

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def originate(self):
        # app=
        # callerId
        endpoint = "SIP/{}".format(cp.request.json['endpoint'])
        self.client().channels.originate(
            endpoint=endpoint,
            extension=cp.request.json['extension'],
            context=cp.request.json['context'],
        )

def connect_ariclient():
    ws = websocket.WebSocket()
    url = "ws://{host}:{port}/ari/events?api_key={user}:{password}&app={app}".format(
        host=os.environ["ASTERISK_SERVER"],
        port=os.environ["ASTERISK_ARI_PORT"],
        user=os.environ["ASTERISK_ARI_USER"],
        password=os.environ["ASTERISK_ARI_PASSWORD"],
        app=APP_NAME,
    )
    ws.connect(url, sockopts=socket.SO_KEEPALIVE)
    time.sleep(2)
    ariclient = ari.connect('http://{}:{}/'.format(
        os.environ["ASTERISK_SERVER"],
        os.environ["ASTERISK_ARI_PORT"],
    ), os.environ["ASTERISK_ARI_USER"], os.environ["ASTERISK_ARI_PASSWORD"])
    data['client'] = ariclient


def run_ariclient():
    while True:
        try:
            if not data['client']:
                raise KeyError()
            data['client'].run(apps=APP_NAME)
        except Exception:
            try:
                data['client'].close()
            except Exception:
                connect_ariclient()
        time.sleep(1)


if __name__ == '__main__':
    cp.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 80,
    })

    connect_ariclient()
    t = threading.Thread(target=run_ariclient)
    t.daemon = True
    t.start()

    connector = Connector()
    cp.quickstart(connector)
