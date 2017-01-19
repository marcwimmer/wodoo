#!/usr/bin/python
import socket
import select
import time
import sys
import configparser
import os
import ssl
import logging


class HTTPS_ConfigHandler(object):
    def __init__(self, conf_path="/opt/conf/{}.cfg".format(os.path.basename(__file__[:-3]))):
        self.config = configparser.ConfigParser()
        self.sections = ["base_config", "ssl_config"]
        self.conf_path = conf_path

    def write_default_config(self):
        for section in self.sections:
            self.config.add_section(section)
        self.config.set(self.sections[0], "log_level", "DEBUG")
        self.config.set(self.sections[0], "modify_mode", "0")
        self.config.set(self.sections[0], "bind_ip", "0.0.0.0")
        self.config.set(self.sections[0], "bind_port", "8068")
        self.config.set(self.sections[0], "referrer_ip", "tricross.no-ip.org")
        self.config.set(self.sections[0], "referrer_port", "80")
        self.config.set(self.sections[1],
                        "#If https is with a self-signed certificate, activate with verify_certificate",
                        "/path/to/chain-cert.pem")
        self.config.set(self.sections[1], "verify_certificate", "./certs/ca-chain.cert.pem")
        self.config.set(self.sections[1], "ssl_active", "0")
        self.config.set(self.sections[1], "server_private_key", "./certs/192.168.60.157.key.pem")
        self.config.set(self.sections[1], "server_certificate", "./certs/192.168.60.157.cert.pem")
        self.config.set(self.sections[1], "ca_certificate", "./certs/ca-chain.cert.pem")
        with open(self.conf_path, "w+") as f:
            self.config.write(f)

    def get_config(self):
        if not os.path.exists(self.conf_path):
            self.write_default_config()
        self.config.read(self.conf_path)
        return self.config


name = "SSLProxy"
version = "1.0"
# Changing the buffer_size and delay, you can improve the speed and bandwidth.
# But when buffer get to high or delay go too down, you can broke things
c_path = "/opt/conf/proxy.cfg"
if os.path.exists("./debug"):
    c_path = "{}.cfg".format(os.path.basename(__file__[:-3]))

conf = HTTPS_ConfigHandler(conf_path=c_path).get_config()

buffer_size = 8192
delay = 0.00001
forward_to = (
    conf["base_config"]["referrer_ip"],
    int(conf["base_config"]["referrer_port"])
)
# Logging
logger = logging.getLogger("ssl_proxy")
ch = logging.StreamHandler(sys.stdout)
logger.setLevel(getattr(logging, conf["base_config"]["log_level"].upper()))
logger.addHandler(ch)
if conf["base_config"]["log_level"].upper() == "DEBUG":
    for key in conf.keys():
        for k in conf[key]:
            logger.debug("kv : {} -> {} -> {}".format(key, k, conf[key][k]))

modify = False

if conf["base_config"]["modify_mode"] == "1":
    modify = True

logger.debug("modify_mode: {}".format(modify))


class Forward:
    def __init__(self):
        self.forward = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.forward.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.forward.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        ssl_active = bool(int(conf["ssl_config"]["target_ssl_active"])) == 1
        logger.debug("[Forward] ssl_active: {}".format(ssl_active))
        if ssl_active:
            nosslverify = ssl._create_unverified_context()
            # self.forward = ssl.wrap_socket(self.forward,context=nosslverify)
            self.forward = nosslverify.wrap_socket(self.forward)
            # urllib.urlopen("https://no-valid-cert", context=context)

    def start(self, host, port):
        try:
            self.forward.connect((host, port))
            return self.forward
        except Exception as e:
            logger.error(e)
            return False


class TheServer:
    input_list = []
    channel = {}
    s = None

    def __init__(self, host, port):
        self.http = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.http.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.http.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.server.bind((host, port))

        ssl_active = int(conf["ssl_config"]["ssl_active"])
        logger.debug("[Server] ssl_active: {}".format(ssl_active))
        if ssl_active == 1:
            logger.debug("loading_ssl")
            import ssl
            key = conf["ssl_config"]["server_private_key"]
            cer = conf["ssl_config"]["server_certificate"]
            cac = conf["ssl_config"]["ca_certificate"]
            req = bool(int(conf["ssl_config"]["client_cert_required"]))
            logger.debug("""
key:    {} ({})
cert:   {} ({})
cac:    {} ({})
req:    {} ({})
                """.format(key, os.path.exists(key), cer, os.path.exists(cer), cac, os.path.exists(cac), req,
                           type(req)))
            cert_req = ssl.CERT_NONE
            if req:
                cert_req = ssl.CERT_REQUIRED
            self.server = ssl.wrap_socket(
                self.server,
                keyfile=key,
                certfile=cer,
                ca_certs=cac,
                ssl_version=ssl.PROTOCOL_TLSv1_2,
                cert_reqs=cert_req)

        self.server.listen(200)

    def main_loop(self):
        logger.debug("Entering main_loop")
        self.input_list.append(self.server)
        while 1:
            time.sleep(delay)
            ss = select.select
            inputready, outputready, exceptready = ss(self.input_list, [], [])
            for self.s in inputready:
                if self.s == self.server:
                    logger.debug("self.s == self.server")
                    self.on_accept()
                    break

                self.data = self.s.recv(buffer_size)
                logger.debug("self.data = {}".format(self.data))
                if len(self.data) == 0:
                    self.on_close()
                    break
                else:
                    self.on_recv()

    def on_accept(self):
        forward = Forward().start(forward_to[0], forward_to[1])
        try:
            clientsock, clientaddr = self.server.accept()
            logger.debug("""
client_sock:    {}
client_addr:    {}
""".format(clientsock, clientaddr))
            client_cert = clientsock.getpeercert()
            logger.debug("subject 3 0 = {}".format(client_cert["subject"][3][0][0]))
            out = ""
            if client_cert["subject"][3][0][0] == "commonName":
                out = "{} Connected".format(client_cert["subject"][3][0][1])
            if client_cert["subject"][0][0][0] == "countryName":
                out += " from {}".format(client_cert["subject"][0][0][1])
            logger.debug(out)
            logger.debug("PeerCert: {}".format(client_cert))
            # logger.info(clientaddr, "has connected")
        except Exception as e:
            logger.warning(e)
            return

        if forward:
            self.input_list.append(clientsock)
            self.input_list.append(forward)
            self.channel[clientsock] = forward
            self.channel[forward] = clientsock
        else:
            logger.warning("Can't establish connection with remote server.")
            logger.info("Closing connection with client side", clientaddr)
            clientsock.close()

    def on_close(self):
        # remove objects from input_list
        logger.debug(self.channel)
        self.input_list.remove(self.s)
        self.input_list.remove(self.channel[self.s])
        out = self.channel[self.s]
        # close the connection with client
        self.channel[out].close()  # equivalent to do self.s.close()
        # close the connection with remote server
        self.channel[self.s].close()
        # delete both objects from channel dict
        del self.channel[out]
        del self.channel[self.s]

    def modify_data(self, data):
        try:
            data = data.replace(b'<head>', b'<head><script type="text/javascript>alert("Testx","Testy","Testz")"')
            logger.debug("Data replaced...")
            logger.debug(data)
            return data
        except Exception as e:
            logger.warning(e)
            logger.warning("Data not replaced...")
            return data

    def on_recv(self):
        logger.debug("Receiving data")
        data = self.data
        # here we can parse and/or modify the data before send forward
        logger.debug(data)
        logger.debug(type(data))
        if modify:
            try:
                data = self.modify_data(data)
            except Exception as e:
                logger.error(e)
        self.channel[self.s].send(data)


def worker():
    logger.debug("Starting Worker! 0xa0001")
    server = TheServer(
        conf["base_config"]["bind_ip"],
        # "192.168.1.53",
        int(conf["base_config"]["bind_port"])
    )
    logger.info("Starting {}({}) ...".format(name, version))
    logger.info("listening on: {} at {}".format(conf["base_config"]["bind_ip"], conf["base_config"]["bind_port"]))
    # try:
    server.main_loop()
    # except Exception as e:
    #    logger.debug(e)
    logger.debug("Exiting Worker! 0x00008")


if __name__ == '__main__':
    try:
        worker()
        logger.info("Exiting! 0x00009")
    except KeyboardInterrupt:
        logger.info("Ctrl C - Stopping server")
        sys.exit(1)
