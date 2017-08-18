# -*- coding: utf-8 -*-
import web
import json
import os
import subprocess
import base64
import process_config

urls = (
    '/', 'index',
    '/generate', 'keygenerator',
    '/repack', 'keygenerator',
    '/setup_ccd', 'setup_ccd'
)
app = web.application(urls, globals())

class index:
    def GET(self):
        return """Please use /generate?client_name=...&conf_template=...&conf_filename=...&tar=0/1 to generate client certificates"""

class setup_ccd:
    def GET(self):
        data = web.input(
            client_name="",
            offset_ip='-1',
            dns=None,
        )

        if not data['client_name']:
            raise Exception("missing name!")

        if data['offset_ip'] not in ['-1', -1]:
            fixed_ip = process_config.get_next_ip(long(data['offset_ip']))
        else:
            fixed_ip = None

        process_config.setup_ccd(
            data['client_name'],
            dns=data.get('dns', None),
            fixed_ip=fixed_ip,
        )

class keygenerator:
    def GET(self):
        data = web.input(
            client_name="",
            conf_template="",
            conf_filename="",
            tar='0'
        )
        if not data.client_name:
            raise Exception("Please provide query-string client_name")

        conf_filename = data.conf_filename
        tar = data.tar == '1'
        if tar and not conf_filename.endswith(".tar"):
            conf_filename += '.tar'

        assert '/' not in conf_filename

        if web.ctx['path'] == '/generate':
            subprocess.check_output([
                '/usr/local/bin/make_client_key.sh',
                data.client_name,
            ])

        subprocess.check_output([
            '/usr/local/bin/pack_client_conf.sh',
            data.client_name,
            data.conf_template,
            conf_filename,
            '-tar' if tar else '',
        ])

        try:
            dest_file_path = os.path.join(os.environ['CLIENT_OUT'], conf_filename)

            with open(dest_file_path, 'r') as f:
                content = f.read()
                content = base64.b64encode(content)
        finally:
            os.unlink(dest_file_path)
        return content


if __name__ == "__main__":
    print "Starting ovpn key generator"
    app.run()
