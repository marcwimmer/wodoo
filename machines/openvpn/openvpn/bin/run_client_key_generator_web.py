# -*- coding: utf-8 -*-
import web
import json
import os
import subprocess

urls = ('/', 'keygenerator')
app = web.application(urls, globals())

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

        subprocess.check_output([
            '/usr/local/bin/pack_client_conf.sh',
            data.client_name,
            data.conf_template,
            conf_filename,
            '-tar' if tar else '',
        ])

        return 'hello world'


if __name__ == "__main__":
    app.run()
