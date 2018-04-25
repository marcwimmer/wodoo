#!/usr/bin/env python
# -*- coding:utf-8 -*-
import os
import re
import sqlalchemy
from sqlalchemy import MetaData
from sqlalchemy.sql import and_
import paho.mqtt.client as mqtt
import subprocess
import json
import logging


ARI_APP_NAME = "asterisk_odoo_connector2"
DOCKER_HOST = subprocess.check_output(["route | awk '/^default/ { print $2 }'"], shell=True).strip()
if os.getenv("ASTERISK_SERVER", "") == "DOCKER_HOST":
    os.environ['ASTERISK_SERVER'] = DOCKER_HOST

FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
logging.basicConfig(format=FORMAT)
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger('')  # root handler

logger.info("Using Asterisk Server on {}".format(DOCKER_HOST))

class MQTT_Connector(object):
    def __init__(self):
        self.mqtt_broker = os.environ["MQTT_BROKER_HOST"]
        self.mqtt_port = int(os.environ.get("MQTT_BROKER_PORT", 1883))
        self.mqtt_user = os.environ.get("MQTT_BROKER_USERNAME", "")
        self.mqtt_pass = os.environ.get("MQTT_BROKER_PASSWORD")
        self.mqttclient = mqtt.Client(
            client_id=os.environ['HOSTNAME'],
            clean_session=False,
            userdata=None,
            protocol=mqtt.MQTTv311
        )
        self.pbxdb = FPBXDBConnector(conf_path=os.environ.get("FPBX_DB_CONF"))
        self.pbxdb.connect()

    def publish(self, topic, payload):
        print("Sending {} auf: {}".format(payload, topic))
        self.mqttclient.publish(topic, payload, qos=2, retain=True)

    def apply_db_changes(self):
        logger.debug("applying database changes")
        cmd = "/usr/sbin/fwconsole reload"
        p = subprocess.check_output(cmd, shell=True)

    #        self.publish("asterisk/extension/pickupgroup/result",p.strip())
    def update_pickgroup(self,data):
        self.pbxdb.update_pickupgroup(data['extension'], data['pickupgroups'])
        ngrp = self.pbxdb.show_pickupgroup(data['extension'])
        data['pickupgroups'] = ngrp
        self.apply_db_changes()
        data['changes_applied'] = True
        self.publish("asterisk/extension/pickupgroup/result", json.dumps(data))
    def get_pickgroup(self,data):
        ngrp= self.pbxdb.show_pickupgroup(data['extension'])
        data['pickupgroups']=ngrp
        self.publish("asterisk/extension/pickupgroup/result", json.dumps(data))

    def on_message(self,client,userdata,message):
        print(message.topic)
        print(message.payload.decode("utf-8"))
        data = json.loads(message.payload.decode("utf-8"))
        if data.get('cmd',None)=="UPDATE":
            self.update_pickgroup(data)
        elif data.get('cmd',None)=="GET":
            self.get_pickgroup(data)


    def run(self):
        # self.mqttclient.username_pw_set(self.mqtt_user,self.mqtt_pass)
        self.mqttclient.connect(self.mqtt_broker, self.mqtt_port, keepalive=60)
        self.mqttclient.on_message = self.on_message
        self.mqttclient.subscribe("asterisk/extension/pickupgroup")
        self.mqttclient.loop_forever()

class FPBXDBConnector(object):
    def __init__(self, conf_path=None, conf_prefix=None, conf_valpat=None):
        if not conf_path:
            # default freepbx db config path
            conf_path = "/etc/freepbx.conf"
        if not conf_prefix:
            # default freepbx config prefix
            conf_prefix = "$amp_conf['"
        if not conf_valpat:
            # default freepbx config regex for values from line
            conf_valpat = r" '(.*)'"
        self.c_valpat = re.compile(conf_valpat)
        self.c_pref = conf_prefix
        self.c_path = conf_path
        self.db_data = {}
        self.get_logindata()
        self.engine = None
        self.conn = None
        self.metadata = MetaData()

    def get_kv(self, line):
        k = line.split('=')[0][len(self.c_pref):-3]
        v = re.search(self.c_valpat, line)
        if not k or not v:
            return None
        key = k
        val = v.groups()[0]
        return key, val

    def get_logindata(self):
        with open(self.c_path, "r") as f:
            for line in f:
                try:
                    k, v = self.get_kv(line)
                except Exception as e:
                    continue
                self.db_data[k] = v

    def connect(self):
        if self._is_connected():
            return
        try:
            h = self.db_data["ASTERISK_SERVER"]
            d = self.db_data["AMPDBNAME"]
            u = self.db_data["AMPDBUSER"]
            p = self.db_data["AMPDBPASS"]
        except KeyError as e:
            print("Connection Failed.{}".format(e))
            return
        con_str = "mysql://{}:{}@{}/{}".format(u, p, h, d)
        self.engine = sqlalchemy.create_engine(con_str)
        self.conn = self.engine.connect()
        self.metadata = MetaData(self.engine, reflect=True)

    def _is_connected(self):
        if self.conn:
            return True
        return False

    def show_pickupgroup(self, extension_nr):
        table = self.metadata.tables["sip"]
        qry = sqlalchemy.select([table]).where(and_(table.c.id == extension_nr, table.c.keyword == "namedpickupgroup"))
        res = self.conn.execute(qry).fetchone()
        return res["data"]

    def update_pickupgroup(self, extension_nr, npg):
        metadata = MetaData()
        table = sqlalchemy.Table("sip", metadata, autoload=True, autoload_with=self.engine)
        qry = table.update().where(and_(table.c.id == extension_nr, table.c.keyword == "namedpickupgroup")).values(
            data=npg)
        self.conn.execute(qry)


if __name__ == "__main__":
    os.environ["MQTT_BROKER_HOST"] = "192.168.1.71"
    os.environ["MQTT_BROKER_PORT"] = "1883"
    os.environ["MQTT_BROKER_USERNAME"] = "mqtt1"
    os.environ["MQTT_BROKER_PASSWORD"] = "mqttpass1"
    os.environ["HOSTNAME"] = "adb_connector"
    mqtt_con=MQTT_Connector()
    mqtt_con.run()
