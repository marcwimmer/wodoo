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
import re
import Queue
import paho.mqtt.client as mqtt
import paho.mqtt.publish as mqtt_publish
from datetime import datetime
from threading import Lock, Thread

CONST_PERM_DIR = os.environ['PERM_DIR']
dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))) # script directory

mqttclient = None
data_client_lock = threading.Lock()

OUTSIDE_PORT = os.environ['OUTSIDE_PORT']

odoo_queue = Queue.Queue(1000)

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

def clean_number(number):
    return (number or '').strip().replace(' ', '')


class Connector(object):

    def __init__(self):
        self.lock = Lock()
        self.blocked_extensions = set()
        self.extensions = {}

    class ExtensionState(object):
        def __init__(self, parent, extension):
            self.parent = parent
            self.extension = extension
            self.state = "Down"

        def reset(self):
            self.update_state("Down")

        def update_state(self, state, channel=False):
            if 'Ring' == state and channel:
                self.parent.odoo(
                    'asterisk.connector',
                    'store_caller_number_for_channel_id',
                    channel['id'],
                    channel.get('caller', {}).get('number', False),
                    state,
                )

            other_channels = []
            # try to identify session for attended transfers
            if state == "Ringing":
                if channel:
                    number = channel['connected']['number']
                    name = channel['connected']['name']
                    # ignore anonymous call to pick phone, when call is started by frontend
                    if not name and not number:
                        return

            if channel:
                for bridge in self.parent.client().bridges.list():
                    bridge = bridge.json
                    if channel['id'] in bridge['channels']:
                        for channel_id in bridge['channels']:
                            if channel_id != channel['id']:
                                other_channel = self.parent._get_channel(channel_id)
                                if other_channel:
                                    other_channels.append(other_channel)

            if self.state != state:
                self.state = state
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
                    extension = str(channel_json['caller']['number']) # e.g. 80
                    self.extensions.setdefault(extension, Connector.ExtensionState(self, extension))
                    self.extensions[extension].update_state(state=channel_json['state'], channel=channel_json)

    def onChannelDestroyed(self, channel_obj, ev):
        channel = channel_obj.json
        channel['state'] = "Down"
        self.on_channel_change(channel)

    def onChannelStateChanged(self, channel_obj, ev):
        self.on_channel_change(channel_obj.json)

    def odoo(self, *params):
        params = json.dumps(params)

        filename = 'odoo_' + datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f") + '.params'
        with open(os.path.join(CONST_PERM_DIR, filename), 'w') as f:
            f.write(params)
            f.flush()

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
    def get_channel(self):
        return self._get_channel(cp.request.json['id'])

    def _get_channel(self, id):
        channels = [x for x in self.client().channels.list() if x.json['id'] == id]
        return channels[0].json if channels else None

    @cp.tools.json_in()
    @cp.tools.json_out()
    @cp.expose
    def get_active_channel(self):
        number = cp.request.json['number']
        channel = self._get_active_channel(number)
        if channel:
            return channel['id']
        return False

    def _get_active_channel(self, extension):
        current_channels = map(lambda c: c.json, self.client().channels.list())

        channels = filter(lambda c: str(c.get('caller', {}).get('number', False)) == str(extension), current_channels)
        if not channels:
            channels = filter(lambda c: c.get('name', '').startswith("SIP/{}-".format(extension)), current_channels)

        if channels:
            return channels[0]

    @cp.tools.json_in()
    @cp.tools.json_out()
    @cp.expose
    def attended_transfer(self):
        # https://wiki.asterisk.org/wiki/display/AST/Asterisk+13+ManagerAction_Atxfer
        action = {
            "name": 'Atxfer',
            "ActionID": str(uuid.uuid4()),
            "Channel": cp.request.json['channel_id'],
            "Exten": clean_number(cp.request.json['exten']),
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
        if not cp.request.json['endpoint']:
            raise Exception("Endpoint missing!")
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
            'extension_states': self.get_extension_states(),
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
        endpoint = clean_number(cp.request.json['endpoint'])
        endpoint = "SIP/{}".format(endpoint)
        result = self.client().channels.originate(
            endpoint=endpoint,
            extension=clean_number(cp.request.json['extension']),
            context=cp.request.json['context'],
        )
        return result.json['id']  # channel



def odoo_thread():

    def exe(*params):
        def login(username, password):
            socket_obj = xmlrpclib.ServerProxy('%s/xmlrpc/common' % (odoo['host']))
            uid = socket_obj.login(odoo['db'], username, password)
            return uid
        uid = login(odoo['username'], odoo['pwd'])

        socket_obj = xmlrpclib.ServerProxy('%s/xmlrpc/object' % (odoo['host']))
        return socket_obj.execute(odoo['db'], uid, odoo['pwd'], *params)

    while True:
        try:
            files = os.listdir(CONST_PERM_DIR)
            files = sorted(files)
            for filename in files:
                if not filename.startswith("odoo_"):
                    continue
                filepath = os.path.join(CONST_PERM_DIR, filename)
                with open(filepath, 'r') as f:
                    params = json.loads(f.read())
                print 'having params {}'.format(params)
                while True:
                    try:
                        exe(*params)
                    except:
                        msg = traceback.format_exc()
                        logger.error(msg)
                        time.sleep(1)
                    else:
                        os.unlink(filepath)
                        break
        except:
            msg = traceback.format_exc()
            logger.error(msg)
            time.sleep(1)
        time.sleep(0.1)

def on_mqtt_connect(client, userdata, flags, rc):
    logger.info("connected with result code " + str(rc))
    client.subscribe("asterisk/#")

def on_mqtt_message(client, userdata, msg):
    logger.info("%s %s", msg.topic, str(msg.payload))

def mqtt_thread():
    while True:
        try:
            mqttclient = mqtt.Client(client_id="asterisk_connector_receiver",)
            logger.info("Connectiong mqtt to {}:{}".format(os.environ['MOSQUITTO_HOST'], long(os.environ['MOSQUITTO_PORT'])))
            mqttclient.connect(os.environ['MOSQUITTO_HOST'], long(os.environ['MOSQUITTO_PORT']), keepalive=10)
            mqttclient.on_connect = on_mqtt_connect
            mqttclient.on_message = on_mqtt_message
            logger.info("Looping mqtt")
            mqttclient.loop_forever()
        except:
            logger.error(traceback.format_exc())
            time.sleep(1)

def mqtt_send():
    while True:
        try:
            logger.info("publishing")
            mqtt_publish.single("asterisk/test", "payload", qos=2, hostname=os.environ['MOSQUITTO_HOST'], port=long(os.environ['MOSQUITTO_PORT']))
        except:
            logger.error(traceback.format_exc())
        time.sleep(1)

if __name__ == '__main__':
    cp.config.update({
        "server.thread_pool": 1, # important to avoid race conditions
        "server.socket_timeout": 100,
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 80,
    })

    t = threading.Thread(target=odoo_thread)
    t.daemon = True
    t.start()

    t = threading.Thread(target=mqtt_thread)
    t.daemon = True
    t.start()

    t = threading.Thread(target=mqtt_send)
    t.daemon = True
    t.start()

    while True:
        try:
            connector = Connector()
        except Exception:
            logger.error(traceback.format_exc())
            logger.info("Retrying after 1 second")
            time.sleep(1)
        else:
            break
    cp.quickstart(connector)
