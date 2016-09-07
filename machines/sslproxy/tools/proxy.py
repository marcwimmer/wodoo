#!/usr/bin/python
import socket
import select
import time
import sys
import configparser
import os


class HTTPS_ConfigHandler(object):
    def __init__(self, conf_path="/opt/conf/{}.cfg".format(os.path.basename(__file__[:-3]))):
        self.config = configparser.ConfigParser()
        self.sections = ["base_config", "ssl_config"]
        self.conf_path = conf_path

    def write_default_config(self):
        for section in self.sections:
            self.config.add_section(section)
        self.config.set(self.sections[0], "debug_mode", "0")
        self.config.set(self.sections[0], "modify_mode", "0")
        self.config.set(self.sections[0], "bind_ip", "0.0.0.0")
        self.config.set(self.sections[0], "bind_port", "8068")
        self.config.set(self.sections[0], "referrer_ip", "192.168.60.52")
        self.config.set(self.sections[0], "referrer_port", "8069")
        self.config.set(self.sections[0],
                        "#If https is with a self-signed certificate, activate with verify_certificate",
                        "/path/to/chain-cert.pem")
        self.config.set(self.sections[0], "verify_certificate", "./certs/ca-chain.cert.pem")
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


# Changing the buffer_size and delay, you can improve the speed and bandwidth.
# But when buffer get to high or delay go too down, you can broke things
conf=HTTPS_ConfigHandler().get_config()
buffer_size = 8192
delay = 0.00001
forward_to = (
    conf["base_config"]["referrer_ip"],
    int(conf["base_config"]["referrer_port"])
)
debug=False

if conf["base_config"]["debug_mode"] == "1":
    debug=True
#forward_to = ('192.168.60.52', 8069)
#redir_to = ('https://192.168.1.53',8069)

class Forward:
    def __init__(self):
        self.forward = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self, host, port):
        try:
            self.forward.connect((host, port))
            return self.forward
        except Exception as e:
            print(e)
            return False

class TheServer:
    input_list = []
    channel = {}

    def __init__(self, host, port):
        self.http = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.http.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR, 1)
        self.http.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.server.bind((host, port))
        ssl_active = int(conf["ssl_config"]["ssl_active"])
        if ssl_active == 1:
            print("loading_ssl")
            import ssl
            key = conf["ssl_config"]["server_private_key"]
            cer = conf["ssl_config"]["server_certificate"]
            cac = conf["ssl_config"]["ca_certificate"]
            if debug:
                print("""
key:    {} ({})
cert:   {} ({})
cac:    {} ({})

                """.format(key,os.path.exists(key),cer,os.path.exists(cer),cac,os.path.exists(cac)))

            self.server = ssl.wrap_socket(
                self.server,
                keyfile=key,
                certfile=cer,
                ca_certs=cac,
                ssl_version=ssl.PROTOCOL_TLSv1_2)
        self.server.listen(200)

    def main_loop(self):
        self.input_list.append(self.server)
        while 1:
            time.sleep(delay)
            ss = select.select
            inputready, outputready, exceptready = ss(self.input_list, [], [])
            for self.s in inputready:
                if self.s == self.server:
                    self.on_accept()
                    break

                self.data = self.s.recv(buffer_size)
                if len(self.data) == 0:
                    self.on_close()
                    break
                else:
                    self.on_recv()

    def on_accept(self):
        forward = Forward().start(forward_to[0], forward_to[1])
        try:
            clientsock, clientaddr = self.server.accept()
            if debug:
                print("""
client_sock:    {}
client_addr:    {}
""".format(clientsock,clientaddr))
        except Exception as e:
            print("Warning: {}".format(e))
            print("Tried to connect on HTTP: Try to Redirect")
            #forward = Forward().start(redir_to[0],redir_to[1])
            #clientsock,clientaddr = self.server.accept()
            return


        if forward:
            print(clientaddr, "has connected")
            self.input_list.append(clientsock)
            self.input_list.append(forward)
            self.channel[clientsock] = forward
            self.channel[forward] = clientsock
        else:
            print("Can't establish connection with remote server.")
            print("Closing connection with client side", clientaddr)
            clientsock.close()

    def on_close(self):
        print(self.s.getpeername(), "has disconnected")
        #remove objects from input_list
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

    def on_recv(self):
        data = self.data
        # here we can parse and/or modify the data before send forward
        print(data)
        self.channel[self.s].send(data)

if __name__ == '__main__':
        conf = HTTPS_ConfigHandler().get_config()
        server = TheServer(
            conf["base_config"]["bind_ip"],
            #"192.168.1.53",
            int(conf["base_config"]["bind_port"])
        )
        print("Starting Proxyserver...")
        print("listening on: {} at {}".format(conf["base_config"]["bind_ip"],conf["base_config"]["bind_port"]))
        try:
            server.main_loop()
        except KeyboardInterrupt:
            print("Ctrl C - Stopping server")
            sys.exit(1)