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


def setup_docker_host_env_variable():

    # apply DOCKER_HOST to host variables
    for f in ("ASTERISK_SERVER", "MQTT_BROKER_HOST"):
        if os.getenv(f, "") == "DOCKER_HOST":
            os.environ[f] = DOCKER_HOST


if __name__ == "__main__":
    setup_docker_host_env_variable()
    setup_logging()

    from pudb import set_trace
    set_trace()
    # create a user
