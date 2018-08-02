#!/usr/bin/env python
import os
import datetime
import paho.mqtt.client as mqtt
import subprocess
import threading
import json
import logging
import traceback
import websocket
import socket
import time
import ari
import re
import requests
from asterisk.ami import AMIClient, SimpleAction, AutoReconnect, EventListener
import sqlalchemy
from sqlalchemy import MetaData, func
from sqlalchemy.sql import and_
from hashlib import sha256
logger = None

# some globals
DOCKER_HOST = os.environ['DOCKER_HOST']

def setup_logging():
    FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
    logging.basicConfig(format=FORMAT)
    logging.getLogger().setLevel(logging.DEBUG)
    return logging.getLogger('')  # root handler


logger = setup_logging()
logger.info("Using Asterisk Server on {}".format(DOCKER_HOST))


class MQTT_Endpoint(object):
    """
    Base class for talking to MQTT.
    """
    def __init__(self):
        self.mqtt_broker = os.environ["MQTT_BROKER_HOST"]
        self.mqtt_port = int(os.environ.get("MQTT_BROKER_PORT", 1883))
        self.mqtt_user = os.environ.get("MQTT_BROKER_USERNAME", "")
        self.mqtt_pass = os.environ.get("MQTT_BROKER_PASSWORD")

        self.subscriptions = []

        self.mqttclient = mqtt.Client(
            client_id=os.environ['HOSTNAME'] + type(self).__name__,
            clean_session=False,
            userdata=None,
            protocol=mqtt.MQTTv311
        )

    def publish(self, topic, payload):
        print("Sending {} to: {}".format(payload, topic))
        self.mqttclient.publish(topic, payload, qos=2, retain=True)

    def run(self):
        def _run(self):
            self.mqttclient.connect(self.mqtt_broker, self.mqtt_port, keepalive=60)
            for subscription in self.subscriptions:
                self.mqttclient.subscribe(subscription)
            # self.mqttclient.username_pw_set(self.mqtt_user,self.mqtt_pass)
            self.mqttclient.on_message = self.on_message
            self.mqttclient.loop_forever()

        t = threading.Thread(target=_run, args=(self,))
        t.daemon = True
        t.start()

class Asterisk_ACM(MQTT_Endpoint, EventListener):
    """
    This class talks to AMI interface and ARI Interface.

    """
    def __init__(self):
        super(Asterisk_ACM, self).__init__()
        self.ari_server = os.environ["ASTERISK_SERVER"]
        self.ari_port = int(os.environ.get("ASTERISK_ARI_PORT", "8088"))
        self.ari_user = os.environ["ASTERISK_ARI_USER"]
        self.ari_pass = os.environ["ASTERISK_ARI_PASSWORD"]

        self.subscriptions += [
            "asterisk/AMI/send",
            "asterisk/Console/send",
            "asterisk/Console/send/#",
            "asterisk/ari/originate",
        ]

        self.connect_ariclient()
        for logger in logging.Logger.manager.loggerDict.keys():
            logging.getLogger(logger).setLevel(logging.INFO)

        t = threading.Thread(target=self.run_ariclient)
        t.daemon = True
        t.start()

        t = threading.Thread(target=self.run_amiclient)
        t.daemon = True
        t.start()

    def run_Console(self, cmd, id=None):

        cmd = "/usr/bin/ssh -p {} {} \"/usr/sbin/asterisk -x '{}'\"".format(os.environ['ASTERISK_SSH_PORT'], DOCKER_HOST, cmd)
        p = subprocess.check_output(cmd, shell=True)

        if id:
            self.publish("asterisk/Console/result/{}".format(id), p.strip())
            return

    def run_AMI(self, cmd, id=None):
        if not cmd:
            raise Exception("Command missing!")
        logger.debug('using host: {}'.format(DOCKER_HOST))
        client = AMIClient(address=DOCKER_HOST, port=int(os.getenv('ASTERISK_AMI_PORT', '5038')))
        username = os.environ["ASTERISK_AMI_USER"]
        logger.debug('logging in {}'.format(username))
        client.login(username=username, secret=os.environ['ASTERISK_AMI_PASSWORD'])
        logger.info("Command %s", cmd)
        logger.debug('login successful')
        cmd = json.loads(cmd)
        logger.debug("SimpleAction of cmd")
        action = SimpleAction(**cmd)
        out = client.send_action(action).response
        logger.debug("Result: {}".format(out))
        out = str(out).strip()
        success = 'success' in out

        if id:
            result = {'success': success, 'data': out}
            self.publish("asterisk/AMI/result/{}".format(id), json.dumps(result))
            return

    def on_message(self, client, userdata, message):
        try:
            logger.info("New Message %s", message.topic)
            if message.topic.startswith("asterisk/Console/send"):
                mt = message.topic.split("/")
                id = ""
                if len(mt) == 4:
                    id = mt[3]

                self.run_Console(message.payload.decode("utf-8"), id)
            elif message.topic.startswith("asterisk/AMI/send"):
                mt = message.topic.split("/")
                id = ""
                if len(mt) == 4:
                    id = mt[3]

                msg = message.payload.decode("utf-8")
                self.run_AMI(msg, id)
            elif message.topic == 'asterisk/ari/originate':
                params = json.loads(message.payload)
                odoo_instance = params.pop('odoo_instance', False)
                channel = self.ariclient.channels.originate(**params)
                if channel:
                    channel_id = channel.json['id']
                    self.mqttclient.publish('asterisk/ari/originate/result', json.dumps({
                        'channel_id': channel_id,
                        'odoo_instance': odoo_instance,
                        'extension': params['extension'],
                    }))

        except Exception:
            logger.error(traceback.format_exc())

    def on_event(self, event, **kwargs):
        self.publish('asterisk/ami/event/{}'.format(event.name), json.dumps(event.keys))

    def connect_amiclient(self):
        logger.info('connecting amiclient')
        amiclient = AMIClient(address=DOCKER_HOST, port=int(os.getenv('ASTERISK_AMI_PORT', '5038')))
        username = os.environ["ASTERISK_AMI_USER"]
        logger.debug('logging in {}'.format(username))
        amiclient.login(username=username, secret=os.environ['ASTERISK_AMI_PASSWORD'])
        amiclient.add_event_listener(self.on_event, white_list=['Pickup'])
        self.amiclient = amiclient
        AutoReconnect(self.amiclient)

    def connect_ariclient(self):
        logger.info('connecting ariclient')
        ws = websocket.WebSocket()
        url = "ws://{host}:{port}/ari/events?api_key={user}:{password}&app={app}".format(
            host=os.environ["ASTERISK_SERVER"],
            port=os.environ["ASTERISK_ARI_PORT"],
            user=os.environ["ASTERISK_ARI_USER"],
            password=os.environ["ASTERISK_ARI_PASSWORD"],
            app=ARI_APP_NAME,
        )
        while True:
            try:
                ws.connect(url, sockopts=socket.SO_KEEPALIVE)
            except Exception as e:
                logger.info('waiting for url to come online: ' + url)
                logger.exception(e)
                time.sleep(1)
            else:
                break
        time.sleep(2)
        ariclient = ari.connect('http://{}:{}/'.format(
            os.environ["ASTERISK_SERVER"],
            os.environ["ASTERISK_ARI_PORT"],
        ), os.environ["ASTERISK_ARI_USER"], os.environ["ASTERISK_ARI_PASSWORD"])
        ariclient.channels.list()
        # ariclient.applications.subscribe(applicationName=[ARI_APP_NAME], eventSource="bridge:")  # or just endpoint:
        # OMG: if freepbx is empty, then registering endpoint:SIP fails (3 hours gone)
        ariclient.applications.subscribe(applicationName=[ARI_APP_NAME], eventSource="endpoint:,bridge:,channel:")  # or just endpoint:

        ariclient.on_channel_event("ChannelCreated", self.onChannelCreated)
        ariclient.on_channel_event("ChannelStateChange", self.onChannelStateChanged)
        ariclient.on_channel_event("ChannelDestroyed", self.onChannelDestroyed)
        ariclient.on_channel_event("ChannelEnteredBridge", self.onBridgeEntered)
        ariclient.on_bridge_event("ChannelLeftBridge", self.onBridgeLeft)
        ariclient.on_bridge_event("BridgeAttendedTransfer", self.onBridgeAttendedTransfer)
        ariclient.on_bridge_event("BridgeBlindTransfer", self.onBridgeBlindTransfer)
        self.ariclient = ariclient

    def onBridgeAttendedTransfer(self, legs, ev, *args, **kwargs):
        self.publish("asterisk/ari/attended_transfer_done", json.dumps({
            'event': ev,
        }))

    def onBridgeBlindTransfer(self, *args, **kwargs):
        print('************************************************************************************************************************************')
        print('************************************************************************************************************************************')
        print('************************************************************************************************************************************')
        print('************************************************************************************************************************************')
        raise Exception("TODO BlindTransfer")
        print('************************************************************************************************************************************')
        print('************************************************************************************************************************************')
        print('************************************************************************************************************************************')
        print('************************************************************************************************************************************')

    def onBridgeEntered(self, channel, ev):
        bridge = ev['bridge']
        self.publish("asterisk/ari/channels_connected", json.dumps({
            'channel_ids': bridge['channels'],
            'channel_entered': channel.json,
        }))

    def onBridgeLeft(self, channel, ev):
        bridge = ev['bridge']
        self.publish("asterisk/ari/channels_disconnected", json.dumps({
            'channel_ids': bridge['channels'],
            'channel_left': channel.json,
        }))

    def onChannelDestroyed(self, channel_obj, ev):
        channel = channel_obj.json
        channel['state'] = "Down"
        self.on_channel_change(channel)

    def onChannelCreated(self, channel_obj, ev):
        self.on_channel_change(channel_obj.json)

    def onChannelStateChanged(self, channel_obj, ev):
        self.on_channel_change(channel_obj.json)

    def on_channel_change(self, channel_json):
        self.publish("asterisk/ari/channel_update", json.dumps(channel_json))

    def _get_channel(self, id):
        channels = [x for x in self.ariclient().channels.list() if x.json['id'] == id]
        return channels[0].json if channels else None

    def run_amiclient(self):
        try:
            self.connect_amiclient()
            logger.info('after connect')
        except Exception:
            logger.error(traceback.format_exc())
            time.sleep(5)
            self.run_amiclient()
        while True:
            time.sleep(1)

    def run_ariclient(self):
        while True:
            logger.info("Run Ari Client")
            try:
                self.ariclient.run(apps=ARI_APP_NAME)
            except Exception:
                try:
                    if self.ariclient:
                        self.ariclient.close()
                except Exception:
                    msg = traceback.format_exc()
                    logger.error(msg)
                    time.sleep(2)

                self.ariclient = None
                while True:
                    try:
                        self.connect_ariclient()
                    except Exception:
                        msg = traceback.format_exc()
                        logger.error(msg)
                        time.sleep(2)
                    else:
                        break
            time.sleep(1)

class FreepbxConnector(MQTT_Endpoint):
    def __init__(self, conf_path=None, conf_prefix=None, conf_valpat=None):
        super(FreepbxConnector, self).__init__()
        self.subscriptions += [
            'asterisk/pickupgroup',
            'asterisk/man_extension',
        ]

    def on_message(self, client, userdata, message):
        # Freepbx 15 provides rest api
        logger.info(message.topic)
        logger.info(message.payload.decode("utf-8"))
        data = json.loads(message.payload.decode("utf-8"))
        if message.topic == "asterisk/pickupgroup":
            if data.get('cmd', None) == "UPDATE":
                self.update_pickgroup(data)
            if data.get('cmd', None) == "REMOVE":
                self.remove_pickupgroup(data)
            if data.get('cmd', None) == "CREATE":
                self.create_pickupgroup(data)
            elif data.get('cmd', None) == "GET":
                self.get_pickgroup(data)

        elif message.topic == "asterisk/man_extension":
            logger.debug("Received Message: %r", data)
            if data.get('cmd', None) == "CREATE":
                self.create_extension(data.get("ext_data", {}))
            if data.get('cmd', None) == "UPDATE":
                self.update_extension(data.get("ext_data", {}))
            if data.get('cmd', None) == "REMOVE":
                self.remove_extension(data.get("ext_data", {}))
            if data.get('cmd', None) == "GET":
                self.get_extension(data.get("ext_data", {}))
        else:
            logger.error("Invalid Topic!")

def setup_docker_host_env_variable():

    # apply DOCKER_HOST to host variables
    for f in ("ASTERISK_SERVER", "MQTT_BROKER_HOST", "FREEPBX_WEB_HOST"):
        if os.getenv(f, "") == "DOCKER_HOST":
            os.environ[f] = DOCKER_HOST


if __name__ == "__main__":
    ARI_APP_NAME = os.getenv('APP_NAME')
    if not ARI_APP_NAME:
        raise Exception("Missing app-name: {}".format(ARI_APP_NAME))

    setup_docker_host_env_variable()
    setup_logging()

    Asterisk_ACM().run()
    #FreepbxConnector().run()
    while True:
        time.sleep(20000)
