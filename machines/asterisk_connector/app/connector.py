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
from threading import Thread
from threading import Timer
import redis
from redis import StrictRedis
from redisworks import Root as Redis
from functools import wraps

odoo_data = {}
odoo_data['uid'] = None
REDIS_HOST = 'redis'
EXPIRE_CHANNEL = 3600 * 24 # seconds
redis_connection_pool = redis.BlockingConnectionPool(host=os.environ['REDIS_HOST'])

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
    number = number.replace("+", "00")
    return (number or '').strip().replace(' ', '')


class throttle(object):
    """
    Decorator that prevents a function from being called more than once every
    time period.
    To create a function that cannot be called more than once a minute:
        @throttle(minutes=1)
        def my_fun():
            pass
    """
    def __init__(self, seconds=0, minutes=0, hours=0):
        self.throttle_period = timedelta(
            seconds=seconds, minutes=minutes, hours=hours
        )
        self.time_of_last_call = datetime.min

    def __call__(self, fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            now = datetime.now()
            time_since_last_call = now - self.time_of_last_call

            if time_since_last_call > self.throttle_period:
                self.time_of_last_call = now
                return fn(*args, **kwargs)

        return wrapper

def exe(*params):
    started = datetime.now()

    socket_obj = xmlrpclib.ServerProxy('%s/xmlrpc/object' % (odoo['host']))
    try:
        result = socket_obj.execute(odoo['db'], odoo_data['uid'], odoo['pwd'], *params)
    except Exception as e:
        if 'MissingError' in str(e) and 'on_channel_originated' in params:
            return
        logger.error("Odoo Error")
        for v in params:
            logger.error(v)
        raise

    logger.info("ODOO call took {}".format((datetime.now() - started).total_seconds()))
    return result

class Connector(object):

    def __init__(self):
        # initially load status
        self.ask_for_dnd()

    def try_to_get_channels(self, channel_ids):
        channels = []
        for channel_id in channel_ids:
            channel = self._get_channel(channel_id)
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
        if not channel_json:
            return

        redisStrict = redis.StrictRedis(connection_pool=redis_connection_pool)
        id = channel_json['id']
        pipeline = redisStrict.pipeline()
        pipeline.sadd('channel_ids', id)
        pipeline.setex(name='channel_creation_date,{}'.format(id), value=channel_json['creationtime'], time=EXPIRE_CHANNEL)
        current_value = self._get_channel(id) or {}
        for k, v in channel_json.items():
            current_value[k] = v
        current_value = json.dumps(current_value)
        pipeline.setex(name='channel,{}'.format(id), value=current_value, time=EXPIRE_CHANNEL)
        pipeline.execute()

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
        return self._get_channel(id)

    def _get_channel(self, id):
        redisStrict = redis.StrictRedis(connection_pool=redis_connection_pool)
        result = redisStrict.get('channel,{}'.format(id))
        if result:
            result = json.loads(result)
        return result

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
        redisStrict = redis.StrictRedis(connection_pool=redis_connection_pool)
        critdate = arrow.get(datetime.now() - timedelta(days=1)).replace(tzinfo='utc').datetime

        data = {
            'date_reached': False,
        }

        def filter_channel(channel_id):
            if data['date_reached']:
                return False

            channel = self._get_channel(channel_id)
            if not channel:
                return False
            if channel['state'] == "Down":
                return False
            if arrow.get(channel['creationtime']).datetime < critdate:
                data['date_reached'] = True
                return False
            return channel

        channel_ids = redisStrict.smembers('channel_ids')
        current_channels = filter(lambda x: bool(x), map(filter_channel, sorted(channel_ids, reverse=True)[:500])) # TBD 500 entries should be enough

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
        redisStrict = redis.StrictRedis(connection_pool=redis_connection_pool)
        exts = set()
        for line in payload.split("\n"):
            line = line.strip()
            if line.startswith("/DND/"):
                extension = line.split("/DND/")[-1].split(":")[0].strip()
                redisStrict.sadd('DND', extension)
                exts.add(extension)
        for x in redisStrict.smembers("DND"):
            if x not in exts:
                redisStrict.srem('DND', x)

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def dnd(self):
        redisStrict = redis.StrictRedis(connection_pool=redis_connection_pool)
        self.adminconsole("DND-State", "database show dnd", 'Console')
        result = list(redisStrict.smembers('DND') or [])
        return result

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def get_state(self):
        redisStrict = redis.StrictRedis(connection_pool=redis_connection_pool)

        self.adminconsole("sip show channels", "sip show channels", "Console")
        dnds = list(redisStrict.smembers('DND') or [])
        return {
            'extension_states': self.get_extension_states(),
            'channels': redisStrict.smembers('channel_ids'),
            'dnds': dnds,
        }

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

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def accept_call(self):
        # does not work
        channel_name = cp.request.json['channel_name']
        action = {
            "name": 'AGI',
            "ActionID": str(uuid.uuid4()),
            "Channel": channel_name,
            "Command": "ANSWER",
            "CommandID": "test",
        }
        self.adminconsole(None, action, 'AMI')

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def reject_call(self):
        # does not work
        channel_id = cp.request.json['channel_id']
        action = {
            "name": 'AGI',
            "ActionID": str(uuid.uuid4()),
            "Channel": channel_id,
            "Command": "REJECT",
        }
        self.adminconsole(None, action, 'AMI')

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def create_pickupgroup(self):
        extensions = cp.request.json["extensions"]
        pickupgroup = cp.request.json["pickupgroup"]
        out = {"cmd": "CREATE", "pickupgroup": pickupgroup, "extensions": extensions}
        mqttclient.publish('asterisk/pickupgroup', payload=json.dumps(out), qos=2)

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def update_pickupgroup(self):
        extensions = cp.request.json["extensions"]
        pickupgroup = cp.request.json["pickupgroup"]
        out = {"cmd": "UPDATE", "pickupgroup": pickupgroup, "extensions": extensions}
        mqttclient.publish('asterisk/pickupgroup', payload=json.dumps(out), qos=2)

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def remove_pickupgroup(self):
        extensions = cp.request.json["extensions"]
        pickupgroup = cp.request.json["pickupgroup"]
        out = {"cmd": "REMOVE", "pickupgroup": pickupgroup, "extensions": extensions}
        mqttclient.publish('asterisk/pickupgroup', payload=json.dumps(out), qos=2)

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def create_extension(self):
        ext_data = cp.request.json["ext_data"]
        out = {"cmd": "CREATE", "ext_data": ext_data}
        mqttclient.publish('asterisk/man_extension', payload=json.dumps(out), qos=2)

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def update_extension(self):
        ext_data = cp.request.json["ext_data"]
        out = {"cmd": "UPDATE", "ext_data": ext_data}
        mqttclient.publish('asterisk/man_extension', payload=json.dumps(out), qos=2)

    @cp.expose
    @cp.tools.json_in()
    @cp.tools.json_out()
    def remove_extension(self):
        ext_data = cp.request.json["ext_data"]
        out = {"cmd": "REMOVE", "ext_data": ext_data}
        mqttclient.publish('asterisk/man_extension', payload=json.dumps(out), qos=2)


@throttle(seconds=2)
def odoo_bus_send_channel_state():
    exe("asterisk.connector", "send_channel_state")


def odoo_thread():

    while not odoo_data['uid']:
        try:
            def login(username, password):
                socket_obj = xmlrpclib.ServerProxy('%s/xmlrpc/common' % (odoo['host']))
                uid = socket_obj.login(odoo['db'], username, password)
                return uid
            odoo_data['uid'] = login(odoo['username'], odoo['pwd'])
        except Exception:
            msg = traceback.format_exc()
            logger.error(msg)
        finally:
            time.sleep(2)

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
                        break
                    else:
                        os.unlink(filepath)
                        break

                t = threading.Thread(target=odoo_bus_send_channel_state)
                t.daemon = True
                t.start()
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
    client.subscribe("asterisk/ami/event/Pickup")

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

        elif msg.topic.startswith('asterisk/ami/event/'):
            if 'Pickup' == msg.topic.split("/")[-1]:
                # logger.info("AMI EVENT %s", msg.topic)
                data = json.loads(msg.payload)
                # logger.info(json.dumps(data, sort_keys=True, indent=4))
                mqttclient.publish(topic="asterisk/ari/channels_connected", qos=2, payload=json.dumps({
                    'channel_ids': [data['Uniqueid'], data['TargetUniqueid']],  # they are names from AMI, but is converted in try_to_get_channels
                    'channel_entered': {
                        'name': data['Channel'],
                        'id': data['Uniqueid'],
                    },
                }))

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
            PORT = long(os.getenv('MOSQUITTO_PORT', "1883"))
            logger.info("Connectiong mqtt to {}:{}".format(os.environ['MOSQUITTO_HOST'], PORT))
            mqttclient.connect(os.environ['MOSQUITTO_HOST'], PORT, keepalive=10)
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
