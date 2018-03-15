#!/usr/bin/env python3

import os
import paho.mqtt.client as mqtt
import subprocess
import json


class Asterisk_ACM(object):
    def __init__(self):
        self.mqtt_broker = os.environ.get("MQTT_BROKER_HOST","192.168.1.71")
        self.mqtt_port = int(os.environ.get("MQTT_BROKER_PORT", 1883))
        self.mqtt_user = os.environ.get("MQTT_BROKER_USERNAME", "")
        self.mqtt_pass = os.environ.get("MQTT_BROKER_PASSWORD")
        self.ari_server = os.environ.get("ASTERISK_SERVER")
        self.ari_port = int(os.environ.get("ASTERISK_ARI_PORT"))
        self.ari_user = os.environ.get("ASTERISK_ARI_USER")
        self.ari_pass = os.environ.get("ASTERISK_ARI_PASSWORD")

        self.client=mqtt.Client(client_id="Asterisk_ACM",clean_session=False,userdata=None,protocol=mqtt.MQTTv311)

    def run_Console(self,cmd,id=None):

        cmd = "/usr/sbin/asterisk -x \"{}\"".format(cmd)
        p = subprocess.check_output(cmd, shell=True)

        if id:
            self.publish("asterisk/Console/result/{}".format(id),p.strip())
            return
        self.publish("asterisk/Console/result",p)

    def on_message(self,client, userdata, message):
        print("received Message")
        print(message.payload)
        print("on channel")
        print(message.topic)

        if message.topic.startswith("asterisk/Console/send"):
            mt = message.topic.split("/")
            id=""
            if len(mt)==4:
                id=mt[3]

            self.run_Console(message.payload.decode("utf-8"),id)
            #self.publish("asterisk/Console/result",message.payload)

    def publish(self,topic,payload):
        print("Sende {} auf: {}".format(payload,topic))
        self.client.publish(topic,payload,qos=2,retain=True)

    def run(self):
        #self.client.username_pw_set(self.mqtt_user,self.mqtt_pass)
        self.client.connect(self.mqtt_broker,self.mqtt_port,keepalive=60)
        self.client.on_message=self.on_message
        self.client.subscribe("asterisk/AMI/send")
        self.client.subscribe("asterisk/Console/send")
        self.client.subscribe("asterisk/Console/send/#")
        self.client.subscribe("asterisk/ari")
        self.client.loop_forever()


if __name__=="__main__":
    env = os.environ
    #dev version:
    os.environ["MQTT_BROKER_HOST"]= "192.168.1.71"
    os.environ["MQTT_BROKER_PORT"]= "1883"
    os.environ["MQTT_BROKER_USERNAME"]="mqtt1"
    os.environ["MQTT_BROKER_PASSWORD"]="mqttpass1"
    os.environ["ASTERISK_SERVER"] = "127.0.0.1"
    os.environ["ASTERISK_ARI_PORT"] = "8088"
    os.environ["ASTERISK_ARI_USER"] = "ariuser1"
    os.environ["ASTERISK_ARI_PASSWORD"] = "password1"

    acm = Asterisk_ACM()
    acm.run()


