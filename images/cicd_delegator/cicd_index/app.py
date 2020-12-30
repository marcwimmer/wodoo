from flask import Flask
from flask import render_template

import json
from pathlib import Path

app = Flask(
    __name__,
    static_folder='/_static_index_files',
)

@app.route('/')
def index():

    reg = json.loads(Path("/registry.json").read_text())

    return render_template('index.html', sites=reg['sites'])

@app.route('/__start_cicd')
def start_cicd():
    return render_template('start_cicd.html')
