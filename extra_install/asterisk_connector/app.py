#!/usr/bin/env python3

import os
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

ARI_APP_NAME = "asterisk_odoo_connector"
DOCKER_HOST = subprocess.check_output(["route | awk '/^default/ { print $2 }'"], shell=True).strip()
if os.getenv("ASTERISK_SERVER", "") == "DOCKER_HOST":
    os.environ['ASTERISK_SERVER'] = DOCKER_HOST

FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
logging.basicConfig(format=FORMAT)
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger('')  # root handler

class Asterisk_ACM(object):
    def __init__(self):
        self.mqtt_broker = os.environ["MQTT_BROKER_HOST"]
        self.mqtt_port = int(os.environ.get("MQTT_BROKER_PORT", 1883))
        self.mqtt_user = os.environ.get("MQTT_BROKER_USERNAME", "")
        self.mqtt_pass = os.environ.get("MQTT_BROKER_PASSWORD")
        self.ari_server = os.environ["ASTERISK_SERVER"]
        self.ari_port = int(os.environ.get("ASTERISK_ARI_PORT", "8088"))
        self.ari_user = os.environ["ASTERISK_ARI_USER"]
        self.ari_pass = os.environ["ASTERISK_ARI_PASSWORD"]

        self.mqttclient = mqtt.Client(
            client_id=os.environ['HOSTNAME'],
            clean_session=False,
            userdata=None,
            protocol=mqtt.MQTTv311
        )
        self.connect_ariclient()
        for logger in logging.Logger.manager.loggerDict.keys():
            logging.getLogger(logger).setLevel(logging.INFO)

        t = threading.Thread(target=self.run_ariclient)
        t.daemon = True
        t.start()

    def run_Console(self,cmd,id=None):

        cmd = "/usr/bin/ssh {} \"/usr/sbin/asterisk -x '{}'\"".format(DOCKER_HOST, cmd)
        p = subprocess.check_output(cmd, shell=True)

        if id:
            self.publish("asterisk/Console/result/{}".format(id),p.strip())
            return
        self.publish("asterisk/Console/result",p)

    def on_message(self, client, userdata, message):
        try:
            if message.topic.startswith("asterisk/Console/send"):
                mt = message.topic.split("/")
                id=""
                if len(mt)==4:
                    id=mt[3]

                self.run_Console(message.payload.decode("utf-8"),id)
                #self.publish("asterisk/Console/result",message.payload)
            elif message.topic == 'asterisk/ari/originate':
                params = json.loads(message.payload)
                channel = self.ariclient().channels.originate(**params)
                if channel:
                    channel_id = channel.json['id']
                    self.mqttclient.publish('asterisk/ari/originate/result', json.dumps({
                        'channel_id': channel_id,
                        'odoo_instance': odoo_instance,
                    }))

        except Exception:
            logger.error(traceback.format_exc())

    def publish(self,topic,payload):
        print("Sende {} auf: {}".format(payload,topic))
        self.mqttclient.publish(topic,payload,qos=2,retain=True)

    def run(self):
        #self.mqttclient.username_pw_set(self.mqtt_user,self.mqtt_pass)
        self.mqttclient.connect(self.mqtt_broker,self.mqtt_port,keepalive=60)
        self.mqttclient.on_message=self.on_message
        self.mqttclient.subscribe("asterisk/AMI/send")
        self.mqttclient.subscribe("asterisk/Console/send")
        self.mqttclient.subscribe("asterisk/Console/send/#")
        self.mqttclient.subscribe("asterisk/ari")
        self.mqttclient.loop_forever()

    def connect_ariclient(self):
        print 'connecting ariclient'
        import pudb;pudb.set_trace()
        ws = websocket.WebSocket()
        url = "ws://{host}:{port}/ari/events?api_key={user}:{password}&app={app}".format(
            host=os.environ["ASTERISK_SERVER"],
            port=os.environ["ASTERISK_ARI_PORT"],
            user=os.environ["ASTERISK_ARI_USER"],
            password=os.environ["ASTERISK_ARI_PASSWORD"],
            app=ARI_APP_NAME,
        )
        print(url)
        ws.connect(url, sockopts=socket.SO_KEEPALIVE)
        time.sleep(2)
        ariclient = ari.connect('http://{}:{}/'.format(
            os.environ["ASTERISK_SERVER"],
            os.environ["ASTERISK_ARI_PORT"],
        ), os.environ["ASTERISK_ARI_USER"],os.environ["ASTERISK_ARI_PASSWORD"])
        ariclient.applications.subscribe(applicationName=[ARI_APP_NAME], eventSource="endpoint:SIP")
        ariclient.on_channel_event("ChannelCreated", self.onChannelStateChanged)
        ariclient.on_channel_event("ChannelStateChange", self.onChannelStateChanged)
        ariclient.on_channel_event("ChannelDestroyed", self.onChannelDestroyed)
        self.ariclient = ariclient

    def onChannelDestroyed(self, channel_obj, ev):
        print 'hier'
        channel = channel_obj.json
        channel['state'] = "Down"
        self.on_channel_change(channel)

    def onChannelStateChanged(self, channel_obj, ev):
        print 'hier2'
        self.on_channel_change(channel_obj.json)

    def on_channel_change(self, channel_json):
        print 'channel state change'
        self.publish("asterisk/ari/channel_update", json.dumps(channel_json))

    def _get_channel(self, id):
        channels = [x for x in self.ariclient().channels.list() if x.json['id'] == id]
        return channels[0].json if channels else None

    def run_ariclient(self):
        while True:
            import pudb;pudb.set_trace()
            print 'Running ariclient'
            try:
                self.ariclient.run(apps=APP_NAME)
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



if __name__=="__main__":
    acm = Asterisk_ACM()
    acm.run()


