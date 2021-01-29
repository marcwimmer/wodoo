import os
import arrow
from flask import Flask
from flask import render_template
from datetime import datetime
from flask import request


import json
from pathlib import Path

from pymongo import MongoClient
mongoclient = MongoClient(
    'mongo',
    27017,
    username=os.environ['MONGO_USERNAME'],
    password=os.environ['MONGO_PASSWORD'],
)
db = mongoclient.get_database()


app = Flask(
    __name__,
    static_folder='/_static_index_files',
)

def augment_reg(reg):
    for site in reg['sites']:
        last_access_file = Path(os.environ['REGISTRY_SITES']) / site['name'] / 'last_access'
        if last_access_file.exists():
            site['last_access'] = arrow.get(last_access_file.read_text()).to(os.environ['DISPLAY_TIMEZONE'])

@app.route("/sites")
def show_sites():
    db.sites

@app.route("/activate", methods=['GET'])
def active(site):
    site['updated'] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    site['enabled'] = True

@app.route('/register', methods=['POST'])
def register_site(**kwargs):
    import pudb
    pudb.set_trace()
    if request.method == 'POST':
        data = request.form
        db.sites.insert_one(data['site'])

@app.route("/previous_instance", methods=["GET"])
def previous_instance(branch_name):
    db.sites.find_one({"


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
