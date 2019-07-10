# used to read and write to settings
import os
import sys
from pathlib import Path

class MyConfigParser:

    def __init__(self, fileName, debug=False):
        self.fileName = Path(fileName)
        del fileName
        self.debug = debug
        self.fileContents = None
        self.configOptions = dict()
        self.quoteOptions = dict()
        if self.fileName.exists():
            self._open()

    def apply(self, other):
        for k in other.keys():
            self[k] = other[k]

    def clear(self):
        self.quoteOptions.clear()
        self.configOptions.clear()
        with open(self.fileName, 'w') as f:
            f.write("")

    def keys(self):
        return self.quoteOptions.keys()

    def _open(self):
        if not self.fileName.exists():
            return
        try:
            with self.fileName.open() as file:
                for line in file:
                    # If it isn't a comment get the variable and value and put it on a dict
                    if not line.startswith("#") and len(line) > 1:
                        (key, val) = line.rstrip('\n').split('=')
                        val = val.strip()
                        val = val.strip('\"')
                        val = val.strip('\'')
                        self.configOptions[key.strip()] = val
                        if val.startswith("("):
                            self.quoteOptions[key.strip()] = ''
                        else:
                            self.quoteOptions[key.strip()] = '\"'
        except Exception:
            print("ERROR: File " + self.fileName + " Not Found\n")

    def write(self):
        handled_keys = set()
        try:
            # Write the file contents
            if not self.fileName.is_file():
                self.fileName.parent.mkdir(exist_ok=True, parents=True)
                self.fileName.write_text("")
            with self.fileName.open("r+") as file:
                lines = file.readlines()
                # Truncate file so we don't need to close it and open it again
                # for writing
                file.seek(0)
                file.truncate()

                def write_line(key, val):
                    if val is None:
                        raise Exception("None value not allowed for: {}".format(key))
                    return key + "=" + val

                # Loop through the file to change with new values in dict
                for line in lines:
                    if not line.startswith("#") and len(line) > 1:
                        (key, val) = line.rstrip('\n').split('=')
                        key = key.strip()
                        if key in self.configOptions:
                            newVal = self.configOptions[key]

                            # Only update if the variable value has changed
                            if val != newVal:
                                line = write_line(key, newVal)
                        handled_keys.add(key)
                    file.write(line.strip() + "\n")
                for key in self.configOptions.keys():
                    if key not in handled_keys:
                        file.write(write_line(key, self.configOptions[key]).strip() + "\n")
        except IOError as e:
            print("ERROR opening file " + self.fileName + ": " + e.strerror + "\n")

    # Redefinition of __getitem__ and __setitem__

    def __getitem__(self, key):
        try:
            return self.configOptions.__getitem__(key)
        except KeyError:
            if isinstance(key, int):
                keys = self.configOptions.keys()
                return self.configOptions[keys[key]]
            else:
                raise KeyError("Key " + key + " doesn't exist")

    def __setitem__(self, key, value):
        if isinstance(value, list):
            self.quoteOptions[key] = ''
            value_list = '('
            for item in value:
                value_list += ' \"' + item + '\"'
            value_list += ' )'
            self.configOptions[key] = value_list
        else:
            self.quoteOptions[key] = '\"'
            self.configOptions[key] = value

    def get(self, key, default_value=""):
        try:
            return self[key]
        except Exception:
            return default_value
