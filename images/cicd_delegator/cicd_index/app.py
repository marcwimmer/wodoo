import os
import arrow
from flask import jsonify
from flask import Flask
from flask import render_template
from datetime import datetime
from flask import request


import json
from pathlib import Path

from pymongo import MongoClient
mongoclient = MongoClient(
    os.environ["MONGO_HOST"],
    int(os.environ['MONGO_PORT']),
    username=os.environ['MONGO_USERNAME'],
    password=os.environ['MONGO_PASSWORD'],
    connectTimeoutMS=5000, socketTimeoutMS=5000
)
db = mongoclient.get_database('cicd_sites')


app = Flask(
    __name__,
    static_folder='/_static_index_files',
)


@app.route("/sites")
def show_sites():
    return jsonify(db.sites.find())

@app.route("/activate", methods=['GET'])
def active():
    site = request.args.get('site')
    if not site:
        raise Exception("Site missing")
    site = db.sites.find_one({'name': site})
    if not site:
        raise Exception(f"site not found: {site}")
    db.sites.update_one({'_id': site['_id']}, {
        'updated': datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        'enabled': True,
    }, upsert=False)

@app.route('/register', methods=['POST'])
def register_site():
    if request.method == 'POST':
        site = dict(request.form)
        index = db.sites.count_documents({'git_branch': site['git_branch']}) + 1
        site['index'] = index
        db.sites.insert_one(site)
        return jsonify({'result': 'ok'})
    raise Exception("only POST")

@app.route("/previous_instance", methods=["GET"])
def previous_instance():
    branch_name = request.args.get('branch')
    if not branch_name:
        raise Exception("Missing branch_name")
    sites = db.sites.find({"git_branch": branch_name})
    sites = sorted(sites, key=lambda x: x['index'])
    site = {}
    if sites:
        site = sites[-1]
    return jsonify(site)

@app.route("/site", methods=["GET"])
def site():
    site = request.args.get('site')
    if not site:
        raise Exception("Missing site")
    site = db.sites.find_one({'name': site})
    return jsonify(site)

@app.route('/')
def index():

    sites = db.sites.find()

    for site in sites:
        if site.get('updated'):
            site['updated'] = arrow.get(site['updated']).to(os.environ['DISPLAY_TIMEZONE'])
    sites = sorted(sites, key=lambda x: x.get('updated', x.get('last_access', arrow.get('1980-04-04'))), reverse=True)
    sites = list(filter(lambda x: x.get('enabled'), sites))

    return render_template(
        'index.html',
        sites=sites,
        DATE_FORMAT=os.environ['DATE_FORMAT'].replace("_", "%"),
    )

@app.route('/__start_cicd')
def start_cicd():
    return render_template('start_cicd.html')
