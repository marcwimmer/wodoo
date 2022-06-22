import json
import tempfile
import shutil
from pathlib import Path

class ProgramSettings(object):
    def __init__(self, filename):
        self.filename = Path(filename)

    def get(self, name, default_value=None):
        if not self.filename.exists():
            self.filename.write_text("{}")
        data = json.loads(self.filename.read_text().strip() or "{}")
        return data.get(name, default_value)

    def set(self, name, value):
        if isinstance(value, Path):
            value = str(value)
        data = json.loads(self.filename.read_text().strip() or "{}")
        data[name] = value
        file = Path(tempfile.mktemp(suffix='.'))
        file.write_text(json.dumps(data))
        # concurrency support
        shutil.move(file, self.filename)
