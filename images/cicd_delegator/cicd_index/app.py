import os
from operator import itemgetter
import docker as Docker
import arrow
import subprocess
from flask import jsonify
from flask import Flask
from flask import render_template
from datetime import datetime
from flask import request
from bson import ObjectId
from collections import defaultdict
import pymongo
import json
from pathlib import Path
from bson.json_util import dumps

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

docker = Docker.from_env()

class JSONEncoder(json.JSONEncoder):
    # for encoding ObjectId
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)

        return super(JSONEncoder, self).default(o)


app.json_encoder = JSONEncoder

@app.route("/last_access")
def last_access():
    if not request.args.get('site'):
        raise Exception('site missing')
    site = db.sites.find_one({'name': request.args.get('site')})
    if site:
        db.sites.update_one({
            '_id': site['_id'],
        }, {'$set': {
            'last_access': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        }, upsert=False)
    return jsonify({'result': 'ok'})

@app.route("/sites")
def show_sites():
    return jsonify(list(db.sites.find()))

@app.route("/activate", methods=['GET'])
def activate():
    site = request.args.get('site')
    if not site:
        raise Exception("Site missing")
    site = db.sites.find_one({'name': site})
    if not site:
        raise Exception(f"site not found: {site}")
    db.sites.update_one({'_id': site['_id']}, {'$set': {
        'updated': datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        'enabled': True,
    }}, upsert=False)
    return jsonify({'result': 'ok'})

@app.route("/next_instance")
def next_instance_name():
    branch = request.args.get('branch')
    key = request.args.get('key')
    assert branch
    assert key
    sites = list(db.sites.find({
        'git_branch': branch,
        'key': key
    }))
    sites = sorted(sites, key=lambda x: x['index'])

    index = max(list(filter(bool, [x.get('index') for x in sites])) + [0])

    info = {
        'commit_before': '',
    }
    if index:
        site = [x for x in sites if x['index'] == index]
        info['commit_before'] = site[0]['git_sha']
        info['prev_name'] = site[0]['name']
    info['name'] = f"{branch}_{key}_{index + 1}"
    info['index'] = index + 1
    return jsonify(info)

@app.route('/register', methods=['POST'])
def register_site():
    if request.method == 'POST':
        site = dict(request.json)
        sites = db.sites.find({
            "git_branch": site['git_branch'],
            "key": site['key'],
        })
        sites = sorted(sites, key=lambda x: x['index'])
        index = 1
        if sites:
            index = 1 + sites[-1]['index']
        site['enabled'] = False
        site['index'] = index
        site['name'] = f"{site['git_branch']}_{site['key']}_{index}"
        db.sites.insert_one(site)
        return jsonify({'result': 'ok', 'name': site['name']})

    raise Exception("only POST")

@app.route("/previous_active_instance", methods=["GET"])
def previous_active_instance():
    branch_name = request.args.get('branch')
    if not branch_name:
        raise Exception("Missing branch_name")
    sites = db.sites.find({"git_branch": branch_name})
    active_sites = [x for x in sites if x.get('enabled')]
    site = {}
    if active_sites:
        site = active_sites[-1]
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

@app.route("/instance/start")
def start_instance():
    name = request.args['name']
    containers = docker.containers.list(all=True, filters={'name': [name]})
    for container in containers:
        container.start(daemon=True)
    return jsonify({
        'result': 'ok',
    })

@app.route("/instance/stop")
def stop_instance():
    name = request.args['name']
    containers = docker.containers.list(all=False, filters={'name': [name]})
    for container in containers:
        container.stop()
    return jsonify({
        'result': 'ok'
    })

@app.route("/instance/status")
def instance_state():
    name = request.args['name']
    return jsonify({
        'state': 'running' if _get_docker_state(name) else 'stopped'
    })

def _get_docker_state(name):
    docker.ping()
    containers = docker.containers.list(all=True, filters={'name': [name]})
    states = set(map(lambda x: x.status, containers))
    return 'running' in states

@app.route('/')
def index():

    sites = list(db.sites.find({'enabled': True}))

    for site in sites:
        for k in site:
            if not isinstance(site[k], str):
                continue
            try:
                site[k] = arrow.get(site[k]).to(os.environ['DISPLAY_TIMEZONE'])
            except arrow.parser.ParserError:
                continue
    sites = sorted(sites, key=lambda x: x.get('updated', x.get('last_access', arrow.get('1980-04-04'))), reverse=True)
    for site in sites:
        site['docker_state'] = 'running' if _get_docker_state(site['name']) else 'stopped'

    sites_grouped = defaultdict(list)
    for site in sites:
        sites_grouped[site['git_branch']].append(site)
    for site in sites_grouped:
        sites_grouped[site] = sorted(sites_grouped[site], key=lambda x: x['index'], reverse=True)

    return render_template(
        'index.html',
        sites=sites_grouped,
        DATE_FORMAT=os.environ['DATE_FORMAT'].replace("_", "%"),
    )


@app.route('/__start_cicd')
def start_cicd():
    return render_template('start_cicd.html')
