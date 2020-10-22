from flask import Flask
import json
from pathlib import Path

app = Flask(__name__)

@app.route('/')
def index():

    reg = json.loads(Path("/registry.json").read_text())

    links = []
    for reg in reg['sites']:
        links.append(f"<a href='/{reg['name']}'>{reg['name']}</a>")

    return (
        f"Available Sites:<br/>"
        f"{'<br/>'.join(links)}"
    )
