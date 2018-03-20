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
from datetime import timedelta
import arrow
from threading import Lock, Thread

CONST_PERM_DIR = os.environ['PERM_DIR']
dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))) # script directory

mqttclient = None
connector = None


OUTSIDE_PORT = os.environ['OUTSIDE_PORT']

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
        self.extensions = {}
        self.dnds = set()
        self.lock = Lock()
        self.channels = {}
        self.bridges = {}

        # initially load status
        self.ask_for_dnd()

    def try_to_get_channels(self, channel_ids):
        channels = []
        for channel_id in channel_ids:
            channel = self.channels.get(channel_id, None)
            if channel:
                channels.append(channel)
        return channels

    def on_channels_connected(self, channel_ids, channel_entered):
        channels = self.try_to_get_channels(channel_ids)
        self.odoo('asterisk.connector', 'asterisk_channels_connected', channels, channel_entered)

    def on_channels_disconnected(self, channel_ids, channel_left):
        channels = self.try_to_get_channels(channel_ids)
        self.odoo('asterisk.connector', 'asterisk_channels_disconnected', channels, channel_left)

    def on_attended_transfer(self, channel_ids):
        self.odoo('asterisk.connector', 'asterisk_on_attended_transfer', channel_ids)

    def on_channel_change(self, channel_json):
        print
        print
        print channel_json['state'], channel_json['id']
        print
        print
        if not channel_json:
            return
        with self.lock:
            self.channels.setdefault(channel_json['id'], channel_json)
            for k, v in channel_json.items():
                self.channels[channel_json['id']][k] = v

        self.odoo('asterisk.connector', 'asterisk_updated_channel_state', channel_json)

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
    def get_active_channels(self):
        extensions = cp.request.json['extensions']
        result = {}
        for ext in extensions:
            result[ext] = self._get_active_channel(ext)
        return result

    def _get_active_channel(self, extension):
        with self.lock:
            critdate = arrow.get(datetime.now() - timedelta(days=1)).replace(tzinfo='utc').datetime
            current_channels = filter(lambda channel: channel['state'] != 'Down' and arrow.get(channel['creationtime']).datetime > critdate, self.channels.values())

        # channels = filter(lambda c: str(c.get('caller', {}).get('number', '')) == str(extension) or str(c.get('connected', {}).get('number', '')) == str(extension), current_channels)
        channels = filter(lambda c: str(c.get('caller', {}).get('number', '')) == str(extension), current_channels)
        if not channels:
            channels = filter(lambda c: c.get('name', '').startswith("SIP/{}-".format(extension)), current_channels)
        return channels

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
        with self.lock:
            return list(self.dnds)

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def get_state(self):

        self.adminconsole("sip show channels", "sip show channels", "Console")
        with self.lock:
            dnds = self.dnds
        return {
            'extension_states': self.get_extension_states(),
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
        extension = clean_number(cp.request.json['extension'])
        if endpoint == extension: # dont allow call self; originated to self, second channel and so on
            return
        endpoint = "SIP/{}".format(endpoint)
        odoo_instance = cp.request.json.get('odoo_instance', '') or ''
        mqttclient.publish('asterisk/ari/originate', payload=json.dumps(dict(
            endpoint=endpoint,
            extension=extension,
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
        try:
            return socket_obj.execute(odoo['db'], uid, odoo['pwd'], *params)
        except Exception as e:
            if 'MissingError' in str(e) and 'on_channel_originated' in params:
                return
            logger.error("Odoo Error")
            for v in params:
                logger.error(v)
            raise

    while True:
        try:
            files = os.listdir(CONST_PERM_DIR)
            files = sorted(files)
            for filename in files:
                if not filename.startswith("odoo_") or not filename.endswith('.params'):
                    continue
                filepath = os.path.join(CONST_PERM_DIR, filename)
                with open(filepath, 'r') as f:
                    params = json.loads(f.read())
                print 'having params {}'.format(params)
                had_error = False
                while True:
                    try:
                        exe(*params)
                        if had_error:
                            had_error = False
                            logger.info("Odoo is back online and just accepted packages")
                    except Exception:
                        had_error = True
                        msg = traceback.format_exc()
                        logger.error(msg)
                        time.sleep(1)
                    else:
                        os.unlink(filepath)
                        break
        except Exception:
            msg = traceback.format_exc()
            logger.error(msg)
            time.sleep(1)
        time.sleep(0.1)

def on_mqtt_connect(client, userdata, flags, rc):
    logger.info("connected with result code " + str(rc))
    client.subscribe("asterisk/Console/result/#")
    client.subscribe("asterisk/AMI/result/#")
    client.subscribe("asterisk/ari/channel_update")
    client.subscribe("asterisk/ari/channels_connected")
    client.subscribe("asterisk/ari/channels_disconnected")
    client.subscribe("asterisk/ari/attended_transfer_done")
    client.subscribe("asterisk/ari/originate/result")

def on_mqtt_message(client, userdata, msg):
    while not connector:
        time.sleep(1)
    try:
        logger.info("%s %s", msg.topic, str(msg.payload))
        if msg.topic.startswith("asterisk/Console/result/"):
            id = msg.topic.split("/")[3]
            if id == 'DND-State':
                connector.eval_dnd_state(msg.payload)
        elif msg.topic == 'asterisk/ari/originate/result':
            payload = json.loads(msg.payload)
            if payload.get('odoo_instance'):
                model, id = payload['odoo_instance'].split(',')
                channel_id = payload['channel_id']
                extension = payload['extension']
                id = long(id)
                connector.odoo('asterisk.connector', 'on_channel_originated', model, [id], channel_id, extension)
        elif msg.topic == 'asterisk/ari/channel_update':
            payload = json.loads(msg.payload)
            connector.on_channel_change(payload)
        elif msg.topic == 'asterisk/ari/channels_connected':
            payload = json.loads(msg.payload)
            connector.on_channels_connected(
                payload['channel_ids'],
                payload['channel_entered'],
            )
        elif msg.topic == 'asterisk/ari/channels_disconnected':
            payload = json.loads(msg.payload)
            connector.on_channels_disconnected(
                payload['channel_ids'],
                payload['channel_left']
            )
        elif msg.topic == 'asterisk/ari/attended_transfer_done':
            event = json.loads(msg.payload)['event']
            channels = []
            channels += event['transferer_first_leg_bridge']['channels']
            channels += event['transferer_second_leg_bridge']['channels']
            channels += [event['transferer_first_leg']['id']]
            channels = list(set(channels))
            connector.on_attended_transfer(channels)

    except Exception:
        logger.error(traceback.format_exc())

def on_mqtt_disconnect(client, userdata, rc):
    if rc != 0:
        logger.error("Unexpected MQTT disconnection. Will auto-reconnect")

def mqtt_thread():
    global mqttclient
    while True:
        try:
            mqttclient = mqtt.Client(client_id="asterisk_connector_receiver.{}".format(socket.gethostname()),)
            # mqttclient.username_pw_set(os.environ['MOSQUITTO_USER'], os.environ['MOSQUITTO_PASSWORD'])
            logger.info("Connectiong mqtt to {}:{}".format(os.environ['MOSQUITTO_HOST'], long(os.environ['MOSQUITTO_PORT'])))
            mqttclient.connect(os.environ['MOSQUITTO_HOST'], long(os.environ['MOSQUITTO_PORT']), keepalive=10)
            mqttclient.on_connect = on_mqtt_connect
            mqttclient.on_message = on_mqtt_message
            mqttclient.on_disconnect = on_mqtt_disconnect
            logger.info("Looping mqtt")
            mqttclient.loop_forever()
        except Exception:
            logger.error(traceback.format_exc())
            time.sleep(1)


if __name__ == '__main__':
    cp.config.update({
        'global': {
            'environment': 'production',
            'engine.autoreload.on': False,
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
