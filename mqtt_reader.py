
import os
import paho.mqtt.client as mqtt

class Asterisk_MQR(object):
    def __init__(self):
        self.mqtt_broker = os.environ.get("MQTT_BROKER_HOST","192.168.1.71")
        self.mqtt_port = int(os.environ.get("MQTT_BROKER_PORT", 1883))
        self.mqtt_user = os.environ.get("MQTT_BROKER_USERNAME", "")
        self.mqtt_pass = os.environ.get("MQTT_BROKER_PASSWORD")
        self.client = mqtt.Client(client_id="Asterisk_ACM", clean_session=False, userdata=None, protocol=mqtt.MQTTv311)

    def on_message(self,client, userdata, message):
        print("received Message")
        print(message.payload)
        print("on channel")
        print(message.topic)

    def publish(self,topic,payload):
        print("Sende {} auf: {}".format(payload,topic))
        self.client.publish(topic,payload,qos=2,retain=True)

    def run(self):
        self.client.username_pw_set(self.mqtt_user,self.mqtt_pass)
        self.client.connect(self.mqtt_broker,self.mqtt_port,keepalive=60)
        self.client.on_message=self.on_message
        self.client.subscribe("asterisk/AMI/send")
        self.client.subscribe("asterisk/Console/send")
        self.client.subscribe("asterisk/Console/send/#")
        self.client.subscribe("asterisk/ari")
        self.client.subscribe("asterisk/Console/result/#")
        self.client.subscribe("asterisk/AMI/result/#")
        self.client.subscribe("asterisk/ari/channel_update")
        self.client.subscribe("asterisk/ari/channels_connected")
        self.client.subscribe("asterisk/ari/channels_disconnected")
        self.client.subscribe("asterisk/ari/attended_transfer_done")
        self.client.subscribe("asterisk/ari/originate/result")
        self.client.subscribe("asterisk/ami/event/Pickup")
        self.client.subscribe('testchannel')
        self.client.loop_forever()

if __name__=="__main__":
    env = os.environ
    os.environ["MQTT_BROKER_HOST"]= "192.168.1.71"
    os.environ["MQTT_BROKER_PORT"]= "1883"
    os.environ["MQTT_BROKER_USERNAME"]="mqtt1"
    os.environ["MQTT_BROKER_PASSWORD"]="mqttpass1"
    mqr = Asterisk_MQR()
    mqr.run()

