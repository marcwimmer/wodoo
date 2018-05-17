#!/usr/bin/env python
# -*- coding:utf-8 -*-
import os
import paho.mqtt.client as mqtt
import subprocess
import json
import logging
import sqlalchemy
from sqlalchemy import MetaData,func
from sqlalchemy.sql import and_
import re
import subprocess
from hashlib import sha256
import datetime


ARI_APP_NAME = "asterisk_db_connector"
DOCKER_HOST = subprocess.check_output(["route | awk '/^default/ { print $2 }'"], shell=True).strip()
if os.getenv("ASTERISK_SERVER", "") == "DOCKER_HOST":
    os.environ['ASTERISK_SERVER'] = DOCKER_HOST

FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
logging.basicConfig(format=FORMAT)
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger('')  # root handler

#logger.info("Using Asterisk Server on {}".format(DOCKER_HOST))
logger.info("Using Asterisk Server on {}".format(os.getenv("ASTERISK_SERVER")))
class MQTT_Connector(object):
    def __init__(self):
        self.mqtt_broker = os.environ["MQTT_BROKER_HOST"]
        self.mqtt_port = int(os.environ.get("MQTT_BROKER_PORT", 1883))
        self.mqtt_user = os.environ.get("MQTT_BROKER_USERNAME", "")
        self.mqtt_pass = os.environ.get("MQTT_BROKER_PASSWORD")
        self.mqttclient = mqtt.Client(
            client_id="{}_{}".format(os.environ['HOSTNAME'],datetime.datetime.now().strftime("%s")),
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
    def create_pickupgroup(self,data):
        print(data)
        #for ext in data['extensions']:
         #   self.pbxdb.create_pickupgroup(ext,data['pickupgroup'])

    def update_pickgroup(self,data):
        self.pbxdb.update_pickupgroup(data['extensions'], data['pickupgroup'])
        ngrp = self.pbxdb.show_pickupgroup(data['extensions'])
        data['pickupgroup'] = ngrp
        self.apply_db_changes()
        data['changes_applied'] = True
        self.publish("asterisk/pickupgroup/result", json.dumps(data))
    def remove_pickupgroup(self,data):
        print(data)

    def get_pickgroup(self,data):
        ngrp= self.pbxdb.show_pickupgroup(data['extension'])
        data['pickupgroups']=ngrp
        self.publish("asterisk/pickupgroup/result", json.dumps(data))

    def on_message(self,client,userdata,message):
        print(message.topic)
        print(message.payload.decode("utf-8"))
        data = json.loads(message.payload.decode("utf-8"))
        if data.get('cmd',None)=="UPDATE":
            self.update_pickgroup(data)
        if data.get('cmd',None)=="REMOVE":
            self.remove_pickupgroup(data)
        if data.get('cmd',None)=="CREATE":
            self.create_pickupgroup(data)
        elif data.get('cmd',None)=="GET":
            self.get_pickgroup(data)


    def run(self):
        # self.mqttclient.username_pw_set(self.mqtt_user,self.mqtt_pass)
        self.mqttclient.connect(self.mqtt_broker, self.mqtt_port, keepalive=60)
        self.mqttclient.on_message = self.on_message
        self.mqttclient.subscribe("asterisk/pickupgroup")
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
            h = self.db_data["AMPDBHOST"]
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

    def show_extension(self,extension_nr):
        table = self.metadata.tables["sip"]
        qry= sqlalchemy.select([table]).where(table.c.id == extension_nr)
        res = self.conn.execute(qry).fetchall()
        return res

    def add_user(self,**params):
        ##########################
        #  ***** USR DATA *****  #
        ##########################
        #  ***** Required *****  #
        usr_values={}
        usr_values["extension"]=params["extension"]
        usr_values["password"]=params["password"]
        usr_values["outboundcid"]=params["outboundcid"]
        #  ***** Optional *****  #
        usr_values["name"]=params.get("name",params["extension"])
        usr_values["voicemail"]=params.get("voicemail","novm")
        usr_values["ringtimer"]=params.get("ringtimer",0)
        usr_values["noanswer"]=params.get("noanswer","")
        usr_values["recording"]=params.get("recording","")
        usr_values["sipname"]=params.get("sipname","")
        usr_values["noanswer_cid"] = params.get("noanswer_cid", "")
        usr_values["busy_cid"] = params.get("busy_cid", "")
        usr_values["chanunavail_cid"] = params.get("chanunavail_cid", "")
        usr_values["noanswer_dest"] = params.get("noanswer_dest", "")
        usr_values["busy_dest"] = params.get("busy_dest", "")
        usr_values["chanunavail_dest"] = params.get("chanunavail_dest", "")
        usr_values["mohclass"]=params.get("mohclass","default")
        table = self.metadata.tables["users"]
        self.conn.execute(table.insert(), usr_values)


        table = self.metadata.tables["userman_users"]
        qry = sqlalchemy.select([func.count()]).select_from(table)
        last_id=int(self.conn.execute(qry).fetchone()[0])+1
        print("Last ID: {}".format(last_id))
        print("New ID : {}".format(last_id+1))
        usrman_values={}
        usrman_values["id"]=last_id+1
        usrman_values["auth"]=params.get("auth",1)
        usrman_values["authid"]=params.get("authid",None)
        usrman_values["username"]=params["extension"]
        usrman_values["description"]=params.get("description","Autogenerated User")
        usrman_values["password"]=params.get("password","{}".format(sha256("{}".format(datetime.datetime.now())).hexdigest()))
        usrman_values["default_extension"]=params["extension"]
        usrman_values["primary_group"]=params.get("primary_group",None)
        usrman_values["permissions"]=params.get("permissions",None)
        usrman_values["fname"]=params.get("fname",None)
        usrman_values["lname"]=params.get("lname",None)
        usrman_values["displayname"]=params.get("name",params["extension"])
        usrman_values["title"]=params.get("title",None)
        usrman_values["company"]=params.get("company",None)
        usrman_values["department"]=params.get("department",None)
        usrman_values["language"]=params.get("language",None)
        usrman_values["timezone"]=params.get("timezone",None)
        usrman_values["dateformat"]=params.get("dateformat",None)
        usrman_values["timeformat"]=params.get("timeformat",None)
        usrman_values["datetimeformat"]=params.get("datetimeformat",None)
        usrman_values["email"]=params.get("email","")
        usrman_values["cell"]=params.get("cell_phone",None)
        usrman_values["work"]=params.get("work_phone",None)
        usrman_values["home"]=params.get("home_phone",None)
        usrman_values["fax"]=params.get("fax",None)
        self.conn.execute(table.insert(), usrman_values)

        device_values={}
        device_values["id"]=params["extension"]
        device_values["tech"]=params.get("tech","sip")
        device_values["dial"] = params.get("dial", "SIP/{}".format(params["extension"]))
        device_values["devicetype"] = params.get("devicetype", "fixed")
        device_values["user"] = params.get("user", params["extension"])
        device_values["description"]=params.get("name",params["extension"])
        device_values["emergency_cid"]=params.get("emergency_cid","")

        table = self.metadata.tables["devices"]
        self.conn.execute(table.insert(),device_values)

    def add_extension(self,**params):
        ##########################
        #  ***** SIP DATA *****  #
        ##########################
        #  ***** Required *****  #
        sip_values = {}
        sip_values["account"] = (params["account"],33)
        sip_values["secret"] = (params["secret"],2)

        # ***** Optional ***** #
        sip_values["account_code"]=(params.get("accountcode",""),28)
        sip_values["context"] = (params.get("context","from-internal"),5)
        sip_values["dtmfmode"] = (params.get("dtmfmode","rfc2833"),3)
        sip_values["allow"] = (params.get("allow",""),26)
        sip_values["avpf"] = (params.get("avpf","no"),17)
        sip_values["callerid"]=(params.get("callerid","device <{}>".format(sip_values["account"][0])),34)
        sip_values["canreinvite"] = (params.get("canreinvite","no"),4)
        sip_values["defaultuser"] = (params.get("defaultuser",""),7)
        sip_values["deny"] = (params.get("deny","0.0.0.0/0.0.0.0"),29)
        sip_values["dial"] = (params.get("dial","SIP/{}".format(sip_values["account"][0])),27)
        sip_values["disallow"] = (params.get("disallow",""),25)
        sip_values["encryption"] = (params.get("encryption","no"),21)
        sip_values["force_avp"] = (params.get("force_avp","no"),18)
        sip_values["host"] = (params.get("host","dynamic"),6)
        sip_values["icesupport"]= (params.get("icesupport","no"),19)
        sip_values["namedcallgroup"]=(params.get("namedcallgroup","1"),23)
        sip_values["namedpickupgroup"] = (params.get("namedpickupgroup","1"),24)
        sip_values["nat"] = (params.get("nat","no"),12)
        sip_values["permit"]=(params.get("permit","0.0.0.0/0.0.0.0"),30)
        sip_values["port"] = (params.get("port","5060"),13)
        sip_values["qualify"] = (params.get("qualify","yes"),14)
        sip_values["qualifyfreq"]=(params.get("qualifyfreq",60),15)
        sip_values["rtcp_mux"] = (params.get("rtcp_mux","no"),20)
        sip_values["secret_origional"] = (params.get("secret_origional",sip_values["secret"][0]),31)
        sip_values["sendrpid"] = (params.get("sendrpid","pai"),9)
        sip_values["sessiontimers"] = (params.get("sessiontimers","accept"),11)
        sip_values["sipdriver"] = (params.get("sipdriver","chan_sip"),32)
        sip_values["transport"] = (params.get("transport","udp,tcp,tls"),16)
        sip_values["trustrpid"] = (params.get("trustrpid","yes"),8)
        sip_values["type"] = (params.get("type","friend"),10)
        sip_values["videosupport"] = (params.get("videosupport","inherit"),22)

        # ***** Modifying Data to Asterisk DB Schema ***** #
        table = self.metadata.tables["sip"]
        data=[]
        for key in sip_values.keys():
            data.append({"id":sip_values["account"][0],"keyword":key,"data":sip_values[key][0],"flags":sip_values[key][1]})

        self.conn.execute(table.insert(),data)
        self.show_extension(sip_values["account"][0])

    def add_inbound_route(self,**params):
        from sqlalchemy import func

        ir_values={}
        table = self.metadata.tables["incoming"]
        # ****** Automatic Values ****** #
        qry = func.max(table.c.id)
        last_id = int(self.conn.execute(qry).fetchone()[0]) + 1
        print("[inbound_routes] - last_id -> ",last_id)
        ir_values["id"]=last_id

        # ****** Required Values ****** #
        ir_values["extension"] = params["ir_source"]
        ir_values["destination"] = params["ir_target"]
        ir_values["description"] = params["rule_name"]

        # ****** Optional Values ******#
        ir_values["cidnum"]=params.get("cidnum","")
        ir_values["privacyman"]=params.get("privacyman",0)
        ir_values["alertinfo"]=params.get("alertinfo","")
        ir_values["ringing"]=params.get("ringing","")
        ir_values["mohclass"]=params.get("mohclass","default")
        ir_values["grppre"]=params.get("grppre","")
        ir_values["delay_answer"]=params.get("delay_answer","0")
        ir_values["pricid"]=params.get("pricid","")
        ir_values["pmmaxretries"]=params.get("pmmaxretries",3)
        ir_values["pmminlength"]=params.get("pmminlength",10)
        ir_values["reversal"]=params.get("reversal","")
        ir_values["rvolume"]=params.get("rvolume",0)

        self.conn.execute(table.insert(),ir_values)


    def apply_db_changes(self):
        cmd = "/usr/sbin/fwconsole reload"
        p = subprocess.check_output(cmd, shell=True)


    def add_pickupgroup(self,extension_nr,npg):
        # fetching current pickup group
        curr_grps = self.show_extension(extension_nr)
        if curr_grps:
            curr_grps=curr_grps.split(",")
            for grp in curr_grps:
                if npg == grp or len(grp) < 1:
                    return True
            curr_grps=",".join(curr_grps)
            curr_grps+=",{}".format(npg)
            self.set_pickupgroup(extension_nr, curr_grps)
        else:
            self.set_pickupgroup(extension_nr, npg)

    def remove_pickupgroup(self,extension_nr,npg):
        # fetching current pickup groups
        curr_grps = self.show_extension(extension_nr)
        o=[]
        if curr_grps:
            curr_grps=curr_grps.split(",")
            for grp in curr_grps:
                if npg!=grp:
                    o.append(grp)
            curr_grps=",".join(o)
            self.set_pickupgroup(extension_nr, curr_grps)

    def update_pickupgroup(self,extensions,npg):
        pass

    def show_pickupgroup(self, extension_nr):
        table = self.metadata.tables["sip"]
        qry = sqlalchemy.select([table]).where(and_(table.c.id == extension_nr, table.c.keyword == "namedpickupgroup"))
        res = self.conn.execute(qry).fetchone()
        return res["data"]

    def set_pickupgroup(self, extension_nr, npg):
        metadata = MetaData()
        table = sqlalchemy.Table("sip", metadata, autoload=True, autoload_with=self.engine)
        qry = table.update().where(and_(table.c.id == extension_nr, table.c.keyword == "namedpickupgroup")).values(
            data=npg)
        self.conn.execute(qry)


if __name__ == "__main__":
    os.environ["ASTERISK_SERVER"] = "localhost"
    os.environ["MQTT_BROKER_HOST"] = "192.168.1.71"
    os.environ["MQTT_BROKER_PORT"] = "1883"
    os.environ["MQTT_BROKER_USERNAME"] = "mqtt1"
    os.environ["MQTT_BROKER_PASSWORD"] = "mqttpass1"
    os.environ["HOSTNAME"] = "adb_connector"
    mqtt_con=MQTT_Connector()
    mqtt_con.run()
