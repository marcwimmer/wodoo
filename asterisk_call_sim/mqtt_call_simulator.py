#!/usr/bin/env python3

import os
import paho.mqtt.client as mqtt
import json
from time import sleep
from random import randint
import datetime
from hashlib import sha256

class CallSim(object):
    def __init__(self):
        self.mqtt_broker = os.environ.get("MQTT_BROKER_HOST","192.168.1.71")
        self.mqtt_port = int(os.environ.get("MQTT_BROKER_PORT", 1883))
        self.mqtt_user = os.environ.get("MQTT_BROKER_USERNAME", "")
        self.mqtt_pass = os.environ.get("MQTT_BROKER_PASSWORD")
        print("""
Connection_Details:
broker: {}
port:   {}
user:   {}
pass:   {}
""".format(self.mqtt_broker,self.mqtt_port,self.mqtt_user,self.mqtt_pass))
        id = sha256("{}".format(randint(0,20003)).encode("utf-8")).hexdigest()[:10]
        client_id = "Asterisk_OCT.{}".format(id)
        self.client = mqtt.Client(clean_session=True, userdata=None, protocol=mqtt.MQTTv311)
        print(self.client.connect(self.mqtt_broker, self.mqtt_port, keepalive=60))
        print(self.client.subscribe("testchannel"))
        self.client.subscribe("asterisk/ari/channel_update",qos=1)
        #self.subscribe_channels=["asterisk/ari/channel_update"]
        #self.client.subscribe("asterisk/extension/pickupgroup", qos=2)
        self.client.on_message = self.on_message
        self.test_channel = b'{"channel_ids": ["1524572991.8284"], "channel_entered": {"accountcode": "", "name": "Local/FMPR-72@from-internal-00000592;1", "language": "en", "caller": {"name": "72", "number": "72"}, "creationtime": "2018-04-24T14:29:51.505+0200", "state": "Up", "connected": {"name": "0304739290", "number": "0304739290"}, "dialplan": {"priority": 1, "exten": "s", "context": "macro-dial"}, "id": "1524572991.8284"}}'

        self.channel_data={
            "asterisk/ari/channel_update":[
                b'{"accountcode": "", "name": "SIP/sipgate_out-0000154e", "language": "de", "caller": {"name": "015120161905", "number": "015120161905"}, "creationtime": "2018-04-24T14:50:36.515+0200", "state": "Ring", "connected": {"name": "", "number": ""}, "dialplan": {"priority": 1, "exten": "4989215444388", "context": "from-trunk-sip-sipgate_out"}, "id": "1524574236.8328"}',
                b'{"accountcode": "", "name": "SIP/88-0000154f", "language": "de", "caller": {"name": "88", "number": "88"}, "creationtime": "2018-04-24T14:50:36.958+0200", "state": "Ringing", "connected": {"name": "015120161905", "number": "015120161905"}, "dialplan": {"priority": 1, "exten": "88", "context": "from-internal"}, "id": "1524574236.8329"}',
                b'{"accountcode": "", "name": "SIP/88-0000154f", "language": "de", "caller": {"name": "88", "number": "88"}, "creationtime": "2018-04-24T14:50:36.958+0200", "state": "Up", "connected": {"name": "015120161905", "number": "015120161905"}, "dialplan": {"priority": 1, "exten": "88", "context": "from-internal"}, "id": "1524574236.8329"}',
                b'{"accountcode": "", "name": "SIP/sipgate_out-0000154e", "language": "de", "caller": {"name": "015120161905", "number": "015120161905"}, "creationtime": "2018-04-24T14:50:36.515+0200", "state": "Up", "connected": {"name": "", "number": ""}, "dialplan": {"priority": 53, "exten": "s", "context": "macro-dial-one"}, "id": "1524574236.8328"}',
                b'{"channel_ids": ["1524574236.8329"], "channel_entered": {"accountcode": "", "name": "SIP/88-0000154f", "language": "de", "caller": {"name": "88", "number": "88"}, "creationtime": "2018-04-24T14:50:36.958+0200", "state": "Up", "connected": {"name": "015120161905", "number": "015120161905"}, "dialplan": {"priority": 1, "exten": "", "context": "from-internal"}, "id": "1524574236.8329"}}',
                {
                    "channel_ids": ["1524642803.8626", "1524642803.8627"],
                    "channel_entered": {"accountcode": "", "name": "SIP/76-00001604", "language": "de",
                                     "caller": {"name": "76", "number": "76"},
                                     "creationtime": "2018-04-25T09:53:23.083+0200", "state": "Up",
                                     "connected": {"name": "80", "number": "80"},
                                     "dialplan": {"priority": 21, "exten": "s", "context": "macro-dial"},
                                     "id": "1524642803.8626"}}
            ]
        }
    def curr_date(self):
        now = datetime.datetime.now().strftime("%d-%m-%Y-%H-%M-%S").split("-")
        nano= randint(0,999)
        return "{}-{}-{}T{}:{}:{}.{:03d}+0200".format(now[2],now[1],now[0],now[3],now[4],now[5],nano)

    def random_channel_name(self,extension,postfix):
        c=randint(200,20000000)
        try:
            return "SIP/{:02d}-{:08d}{}".format(extension,c,postfix)
        except:
            return "SIP/{}-{:08d}{}".format(extension,c,postfix)

    def send_dummy(self):
        out={"Test":"Nachricht"}
        #self.client.publish(topic, payload, qos=2, retain=True)
        self.publish('testchannel', json.dumps(out))
        #self.publish("asterisk/ari/channel_update/84848",json.dumps(out))

    def get_ringing_channels(self):
        exten = 88
        caller_num = "0123456789"
        c1 = json.loads(
            '{"accountcode": "", "name": "SIP/sipgate_out-0000154e", "language": "de", "caller": {"name": "{0}", "number": "{0}"}, "creationtime": "2018-04-24T14:50:36.515+0200", "state": "Ring", "connected": {"name": "", "number": ""}, "dialplan": {"priority": 1, "exten": "4989215444388", "context": "from-trunk-sip-sipgate_out"}, "id": "1524574236.8328"}')
        c2 = json.loads(
            '{"accountcode": "", "name": "SIP/88-0000154f", "language": "de", "caller": {"name": "88", "number": "88"}, "creationtime": "2018-04-24T14:50:36.958+0200", "state": "Ringing", "connected": {"name": "{0}", "number": "{0}"}, "dialplan": {"priority": 1, "exten": "88", "context": "from-internal"}, "id": "1524574236.8329"}')
        c1["name"] = self.random_channel_name("sipgate_out", "e")
        c2["name"] = self.random_channel_name(88, "f")
        c1["caller"]["name"] = caller_num
        c1["caller"]["number"] = caller_num
        c2["connected"]["name"] = caller_num
        c2["connected"]["number"] = caller_num
        c1["creationtime"] = self.curr_date()
        c2["creationtime"] = self.curr_date()
        return c1,c2

    def send_channel(self,channel):
        self.publish("asterisk/ari/channel_update", json.dumps(channel))

    def channel_ring(self,channel):
        channel["state"]="ring"
        return channel

    def channel_ringing(self,channel):
        channel["state"]="ringing"
        return channel

    def channel_up(self,channel):
        channel["state"]="up"
        return channel

    def channel_down(self,channel):
        channel["state"]="down"
        return channel

    def wait_for_message(self):
        self.client.loop_start()
        sleep(5)
        self.client.loop_stop()

    def publish(self, topic, payload):
        print("Sending {} auf: {}".format(payload, topic))
        self.client.publish(topic, payload, qos=0, retain=False)
        #self.wait_for_message()

    def disconnect(self):
        self.client.disconnect()

    def on_message(self,client,userdata,message):
        print("Receiving")
        print(message.topic)
        print(message.payload.decode("utf-8"))

if __name__=="__main__":
    env = os.environ
    # dev version:
    os.environ["MQTT_BROKER_HOST"]= "192.168.1.71"
    os.environ["MQTT_BROKER_PORT"]= "1883"
    os.environ["MQTT_BROKER_USERNAME"]="mqtt1"
    os.environ["MQTT_BROKER_PASSWORD"]="mqttpass1"

    cs = CallSim()
    c1,c2 = cs.get_ringing_channels()
    c1 = cs.channel_up(c1)
    c2 = cs.channel_up(c2)
    cs.send_channel(c1)
    cs.send_channel(c2)
    count=30
    sleeptime = 5 #in seconds
    c1=cs.channel_ring(c1)
    c2=cs.channel_ringing(c2)
    while count>0:
        cs.send_channel(c1)
        cs.send_channel(c2)
        sleep(sleeptime)
        count -=sleeptime
    c1=cs.channel_down(c1)
    c2=cs.channel_down(c2)
    cs.send_channel(c1)
    cs.send_channel(c2)
    cs.disconnect()