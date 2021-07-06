from datetime import date
import arrow
from pathlib import Path
import json
import shutil
import os
import time
import uuid
from robot.api.deco import keyword



class tools(object):

    def get_guid(self):
        return str(uuid.uuid4())
        
    def get_current_date(self):
        return date.today()

    def get_now(self):
        return arrow.get().datetime

    def copy_file(self, source, destination):
        shutil.copy(source, destination)

    def get_json_content(self, filepath):
        return json.loads(Path(filepath).absolute().read_text())

    def set_dict_key(self, data, key, value):
        data[key] = value    