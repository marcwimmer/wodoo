#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from http.cookies import SimpleCookie
import arrow
import argparse
import os
import random
import sys
import requests
import logging
import json
from pathlib import Path

cicd_index_url = "http://cicd_index:5000"

FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
logging.basicConfig(format=FORMAT)
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger('')  # root handler
logger.info("Starting cicd delegator reverse-proxy")

class ProxyHTTPRequestHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'

    def _merge_headers(self, *arrs):
        headers = sum(arrs)
        return headers

    def do_HEAD(self):
        self.do_GET(body=False)

    def _handle_error(self, ex):
        logger.error(ex)
        self.send_error(501, str(ex))

    def _rewrite_path(self, header):
        url = ""
        if "Cookie" in header:
            cookie = SimpleCookie(header['Cookie'])
            delegator_path = cookie.get('delegator-path', "")
            delegator_path = delegator_path and delegator_path.value
        else:
            delegator_path = 'not-set'
        if delegator_path == 'not-set':
            delegator_path = ""

        if delegator_path:
            # set touched date:
            path = Path(os.environ['REGISTRY_SITES']) / delegator_path / 'last_access'
            path.parent.mkdir(exist_ok=True)
            path.write_text(arrow.get().strftime("%Y-%m-%d %H:%M:%S"))
            del path

        logger.debug(f"rewrite path: self.path: {self.path}, delegator_path: {delegator_path}")

        if self.path in ['/index', '/index/'] or "/__start_cicd" in self.path or not delegator_path:
            path = self.path
            if path.split("/")[1] == 'index':
                path = '/'
            else:
                path = '/' + '/'.join(path.split("/")[2:])
            url = f'{cicd_index_url}{path}'
        else:
            host = f"{delegator_path}_proxy"
            path = self.path.replace(f"/{delegator_path}", "")
            url = f'http://{host}{path}'

        logger.debug(f"rewrite path result: {url}")
        return url

    def do_GET(self, body=True):
        sent = False
        try:
            req_header = self.parse_headers()
            url = self._rewrite_path(req_header)
            logger.debug(f"{url}\n{req_header}")
            resp = requests.get(
                url, headers=req_header, verify=False,
                allow_redirects=False,
            )
            sent = True

            self.send_response(resp.status_code)
            self.send_resp_headers(resp)
            if body:
                self.wfile.write(resp.content)

            return
        except Exception as ex:
            self._handle_error(ex)
        finally:
            self.finish()
            if not sent:
                self.send_error(404, 'error trying to proxy')

    def do_POST(self, body=True):
        req_header = self.parse_headers()
        url = self._rewrite_path(req_header)
        sent = False
        try:
            content_len = int(self.headers.get('content-length', 0))
            post_body = self.rfile.read(content_len)

            resp = requests.post(
                url, data=post_body, headers=req_header,
                verify=False, allow_redirects=False,
            )
            sent = True

            self.send_response(resp.status_code)
            self.send_resp_headers(resp)
            if body:
                self.wfile.write(resp.content)
            return
        finally:
            self.finish()
            if not sent:
                self.send_error(404, 'error trying to proxy')

    def parse_headers(self):
        req_header = {}
        for line in self.headers.as_string().split("\n"):
            if not line:
                continue
            line_parts = [o.strip() for o in line.split(':', 1)]
            if len(line_parts) == 2:
                req_header[line_parts[0]] = line_parts[1]
        return req_header

    def _set_cookies(self, cookie):
        logger.debug(f"Path is: {self.path}")
        reg = self._get_registry()
        sites = list(x['name'] for x in reg['sites'])

        if '/__start_cicd' in self.path:
            site = self.path.split("/")[1]
            if site in sites:
                cookie['delegator-path'] = site
                cookie['delegator-path']['max-age'] = 365 * 24 * 3600
                cookie['delegator-path']['path'] = '/'
        elif self.path in ['/index', '/index/', '/web/session/logout']:
            cookie['delegator-path'] = "not-set"
            cookie['delegator-path']['path'] = '/'

    def send_resp_headers(self, resp):
        cookie = SimpleCookie()
        self._set_cookies(cookie)

        respheaders = resp.headers
        logger.debug('Response Header')
        for key in respheaders:
            if (key or '').lower() not in [
                'content-encoding', 'transfer-encoding', 'content-length'
            ]:
                self.send_header(key, respheaders[key])
        self.send_header('Content-Length', len(resp.content))
        for morsel in cookie.values():
            self.send_header("Set-Cookie", morsel.OutputString())
        self.end_headers()


def parse_args(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(description='Proxy HTTP requests')
    parser.add_argument(
        '--port', dest='port', type=int,
        default=80, help='serve HTTP requests on specified port (default: 80)'
    )
    args = parser.parse_args(argv)
    return args

def main(argv=sys.argv[1:]):
    args = parse_args(argv)
    logger.info('http server is starting on port {}...'.format(args.port))
    server_address = ('0.0.0.0', args.port)
    httpd = ThreadingHTTPServer(server_address, ProxyHTTPRequestHandler)
    logger.info('http server is running as reverse proxy')
    logger.info(f"Starting reverse proxy on {server_address}")
    httpd.serve_forever()


if __name__ == '__main__':
    main()
