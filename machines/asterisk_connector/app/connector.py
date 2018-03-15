# -*- coding: utf-8 -*-
import uuid
import json
import requests
import os
import socket
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
from datetime import datetime
from threading import Lock, Thread

CONST_PERM_DIR = os.environ['PERM_DIR']
dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))) # script directory

mqttclient = None

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

class Connector(object):

    def __init__(self):
        self.lock = Lock()
        self.extensions = {}
        self.dnds = set()
        self.lock = Lock()
        self.channels = {}

        # initially load status
        self.ask_for_dnd()

    def on_channel_change(self, channel_json):
        if channel_json.get('caller', False):
            if channel_json['caller'].get('number', False):
                extension = str(channel_json['caller']['number']) # e.g. 80
                with self.lock:
                    self.extensions.setdefault(extension, ExtensionState(self, extension))
                    self.extensions[extension].update_state(state=channel_json['state'], channel=channel_json)

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

    @cp.tools.json_in()
    @cp.tools.json_out()
    @cp.expose
    def get_channel(self):
        id = cp.request.json['id']
        with self.lock:
            return self.channels.get(id, None)

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
        with self.lock:
            current_channels = filter(lambda channel: channel['state'] != 'Down', self.channels.values())

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
        self.adminconsole(None, action, 'AMI')

    def adminconsole(self, id, cmd, ttype):
        """
        :param id: result gets the same id, e.g. DND-Status
        :param ttype: values: 'AMI', 'Console'

        """
        assert ttype in ['AMI', 'Console']
        if ttype == "AMI":
            assert isinstance(cmd, dict)
            cmd = json.dumps(cmd)
        assert isinstance(cmd, (str, unicode))

        topic = 'asterisk/{}/send'.format(ttype)
        if id:
            topic += '/{}'.format(id)

        mqttclient.publish(topic, payload=cmd, qos=2)
        return None

    @cp.tools.json_in()
    @cp.tools.json_out()
    @cp.expose
    def set_dnd(self):
        if not cp.request.json['endpoint']:
            raise Exception("Endpoint missing!")
        self.adminconsole('set_dnd', "database {verb} DND {endpoint} {dnd}".format(
            endpoint=cp.request.json['endpoint'],
            dnd='YES' if cp.request.json['dnd'] else '',
            verb='put' if cp.request.json['dnd'] else 'del',
        ), 'Console')

    def ask_for_dnd(self):
        self.adminconsole("DND-State", "database show dnd", 'Console')

    def eval_dnd_state(self, payload):
        with self.lock:
            self.dnds = set()
            for line in payload.split("\n"):
                line = line.strip()
                if line.startswith("/DND/"):
                    extension = line.split("/DND/")[-1].split(":")[0].strip()
                    self.dnds.add(extension)

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def dnd(self):
        self.adminconsole("DND-State", "database show dnd", 'Console')
        with lock:
            return list(self.dnds)

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def get_state(self):

        self.adminconsole("sip show channels", "sip show channels", "Console")
        with lock:
            dnds = self.dnds
        return {
            'extension_states': self.get_extension_states(),
            'admin': r,
            'channels': self.channels.values(),
            'dnds': dnds,
        }

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def get_extension_states(self):
        with self.lock:
            return [x.jsonify() for x in self.extensions.values()]

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def originate(self):
        # app=
        # callerId
        endpoint = clean_number(cp.request.json['endpoint'])
        endpoint = "SIP/{}".format(endpoint)
        odoo_instance = cp.request.json.get('odoo_instance', '') or ''
        mqttclient.publish('asterisk/ari/originate', payload=json.dumps(dict(
            endpoint=endpoint,
            extension=clean_number(cp.request.json['extension']),
            context=cp.request.json['context'],
            odoo_instance=odoo_instance,
        )), qos=2)

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
    client.subscribe("asterisk/Console/result/#")
    client.subscribe("asterisk/AMI/result/#")
    client.subscribe("asterisk/ari/channel_update")
    client.subscribe("asterisk/ari/originate/result")

def on_mqtt_message(client, userdata, msg):
    try:
        logger.info("%s %s", msg.topic, str(msg.payload))
        if msg.topic.startswith("asterisk/Console/result/"):
            id = msg.topic.split("/")[3]
            if id == 'DND-State':
                connector.eval_dnd_state(msg.payload)
        elif msg.topic == 'asterisk/ari/originate/result':
            payload = json.loads(msg.payload)
            if payload.get('odoo_instance'):
                model, id = odoo_instance.split(',')
                channel_id = payload['channel_id']
                id = long(id)
                connector.odoo(model, 'on_channel_originated', [id], channel_id)
        elif msg.topic == 'asterisk/ari/channel_update':
            payload = json.loads(msg.payload)
            connector.on_channel_change(payload)
    except:
        logger.error(traceback.format_exc())

def on_mqtt_disconnect(client, userdata, rc):
    if rc != 0:
        logger.error("Unexpected MQTT disconnection. Will auto-reconnect")

def mqtt_thread():
    global mqttclient
    while True:
        try:
            mqttclient = mqtt.Client(client_id="asterisk_connector_receiver",)
            #mqttclient.username_pw_set(os.environ['MOSQUITTO_USER'], os.environ['MOSQUITTO_PASSWORD'])
            logger.info("Connectiong mqtt to {}:{}".format(os.environ['MOSQUITTO_HOST'], long(os.environ['MOSQUITTO_PORT'])))
            mqttclient.connect(os.environ['MOSQUITTO_HOST'], long(os.environ['MOSQUITTO_PORT']), keepalive=10)
            mqttclient.on_connect = on_mqtt_connect
            mqttclient.on_message = on_mqtt_message
            mqttclient.on_disconnect = on_mqtt_disconnect
            logger.info("Looping mqtt")
            mqttclient.loop_forever()
        except:
            logger.error(traceback.format_exc())
            time.sleep(1)


if __name__ == '__main__':
    cp.config.update({
        'global': {
            'environment' : 'production',
            'engine.autoreload.on' : False,
            "server.thread_pool": 1, # important to avoid race conditions
            "server.socket_timeout": 100,
            'server.socket_host': '0.0.0.0',
            'server.socket_port': 80,
          }
    })

    t = threading.Thread(target=odoo_thread)
    t.daemon = True
    t.start()

    t = threading.Thread(target=mqtt_thread)
    t.daemon = True
    t.start()

    while not mqttclient:
        time.sleep(1)
        logger.info("Waiting for mqtt client")

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
