#!/usr/bin/env python3
# -*- coding:utf-8 -*-



import os
import paho.mqtt.client as mqtt
import json
from time import sleep


class OCT(object):
    def __init__(self):
        self.mqtt_broker = os.environ.get("MQTT_BROKER_HOST","192.168.1.71")
        self.mqtt_port = int(os.environ.get("MQTT_BROKER_PORT", 1883))
        self.mqtt_user = os.environ.get("MQTT_BROKER_USERNAME", "")
        self.mqtt_pass = os.environ.get("MQTT_BROKER_PASSWORD")
        self.client = mqtt.Client(client_id="Asterisk_TOCT", clean_session=False, userdata=None, protocol=mqtt.MQTTv311)
        self.client.connect(self.mqtt_broker, self.mqtt_port, keepalive=60)
        self.client.subscribe("asterisk/pickupgroup",qos=2)
        self.client.on_message=self.on_message

    def set_pickup_group(self,extension,new_grp):
        data=json.dumps({"cmd":"CREATE","extensions":extension,"pickupgroup":new_grp})
        print(data)

        self.publish('asterisk/pickupgroup',data)
        print("published")

    def simulate_call(self):
        pass
    def wait_for_message(self):
        self.client.loop_start()
        sleep(5)
        self.client.loop_stop()

    def publish(self, topic, payload):
        print("Sending {} auf: {}".format(payload, topic))
        self.client.publish(topic, payload, qos=2, retain=True)
        self.wait_for_message()

    def on_message(self,client,userdata,message):
        print(message.topic)
        print(message.payload.decode("utf-8"))




if __name__=="__main__":
    env = os.environ
    # dev version:
    os.environ["MQTT_BROKER_HOST"] = "192.168.1.71"
    os.environ["MQTT_BROKER_PORT"] = "1883"
    os.environ["MQTT_BROKER_USERNAME"] = "mqtt1"
    os.environ["MQTT_BROKER_PASSWORD"] = "mqttpass1"

    oct = OCT()
    oct.set_pickup_group([14],221)

