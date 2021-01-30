import os
import arrow
from flask import jsonify
from flask import Flask
from flask import render_template
from datetime import datetime
from flask import request
from bson import ObjectId
from itertools import groupby
import pymongo
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

class JSONEncoder(json.JSONEncoder):
    # for encoding ObjectId
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)

        if isinstance(o, pymongo.cursor.Cursor):
            import pudb
            pudb.set_trace()
            return json.dumps(list(o), cls=JSONEncoder)

        if isinstance(o, dict):
            return json.dumps(o, cls=JSONEncoder)

        return json.JSONEncoder.default(self, o)


app.json_encoder = JSONEncoder

@app.route("/last_access")
def last_access():
    if not request.args.get('site'):
        raise Exception('site missing')
    site = db.sites.find_one({'name': request.args.get('site')})
    if site:
        db.sites.update_one({
            '_id': site['_id'],
        }, {
            'last_access': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }, upsert=False)

@app.route("/sites")
def show_sites():
    import pudb
    pudb.set_trace()
    return jsonify(db.sites.find())

@app.route("/activate", methods=['GET'])
def activate():
    site = request.args.get('site')
    if not site:
        raise Exception("Site missing")
    site = db.sites.find_one({'name': site})
    if not site:
        raise Exception(f"site not found: {site}")
    import pudb
    pudb.set_trace()
    db.sites.update_one({'_id': site['_id']}, {
        'updated': datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        'enabled': True,
    }, upsert=False)

@app.route("/next_instance_name")
def next_instance_name():
    branch = request.args.get('branch')
    key = request.args.get('branch')
    assert branch
    assert key
    sites = db.sites.find({'git_branch': branch})
    index = max(list(filter(bool, [x.get('index') for x in sites])) + [0])
    return f"{site['git_branch']}_{site['key']}_{index}"

@app.route('/register', methods=['POST'])
def register_site():
    if request.method == 'POST':
        site = dict(request.json)
        site['index'] = index
        site['enabled'] = False
        db.sites.insert_one(site)
        return jsonify({'result': 'ok', 'name': site['name']})

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
    q = {}
    for key in [
        'site', 'key', 'branch',
    ]:
        if request.args.get(key):
            q[key] = request.args.get(key)
    site = db.sites.find(q)
    return jsonify(site)

@app.route('/')
def index():

    sites = db.sites.find()

    for site in sites:
        if site.get('updated'):
            site['updated'] = arrow.get(site['updated']).to(os.environ['DISPLAY_TIMEZONE'])
    sites = sorted(sites, key=lambda x: x.get('updated', x.get('last_access', arrow.get('1980-04-04'))), reverse=True)
    sites = list(filter(lambda x: x.get('enabled'), sites))

    sites = groupby(sites, lambda x: x['git_branch'])

    return render_template(
        'index.html',
        sites=sites,
        DATE_FORMAT=os.environ['DATE_FORMAT'].replace("_", "%"),
    )

@app.route('/__start_cicd')
def start_cicd():
    return render_template('start_cicd.html')
