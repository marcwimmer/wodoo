import os
import arrow
from flask import Flask
from flask import render_template

import json
from pathlib import Path

app = Flask(
    __name__,
    static_folder='/_static_index_files',
)

def augment_reg(reg):
    for site in reg['sites']:
        last_access_file = Path(os.environ['REGISTRY_SITES']) / site['name'] / 'last_access'
        if last_access_file.exists():
            site['last_access'] = arrow.get(last_access_file.read_text()).to(os.environ['DISPLAY_TIMEZONE'])


@app.route('/')
def index():

    reg = json.loads(Path("/registry.json").read_text())

    augment_reg(reg)

    for site in reg['sites']:
        if site.get('updated'):
            site['updated'] = arrow.get(site['updated']).to(os.environ['DISPLAY_TIMEZONE'])
    reg['sites'] = sorted(reg['sites'], key=lambda x: x.get('updated', x.get('last_access', arrow.get('1980-04-04'))), reverse=True)
    reg['sites'] = list(filter(lambda x: x.get('enabled'), reg['sites']))

    return render_template(
        'index.html',
        sites=reg['sites'],
        DATE_FORMAT=os.environ['DATE_FORMAT'].replace("_", "%"),
    )

@app.route('/__start_cicd')
def start_cicd():
    return render_template('start_cicd.html')
