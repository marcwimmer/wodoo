# -*- coding: utf-8 -*-
# used to read and write to settings

import os
import sys

class MyConfigParser:
    name = 'MyConfigParser'
    debug = False
    fileName = None
    fileContents = None
    configOptions = dict()
    quoteOptions = dict()

    def __init__(self, fileName, debug=False):
        self.fileName = fileName
        self.debug = debug
        self._open()

    def apply(self, other):
        for k in other.keys():
            self[k] = other[k]

    def keys(self):
        return self.quoteOptions.keys()

    def _open(self):
        if not os.path.exists(self.fileName):
            return
        try:
            with open(self.fileName, 'r') as file:
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
            print "ERROR: File " + self.fileName + " Not Found\n"

    def write(self):
        handled_keys = set()
        try:
            # Write the file contents
            if not os.path.isfile(self.fileName):
                with open(self.fileName, 'w'):
                    pass
            with open(self.fileName, 'r+') as file:
                lines = file.readlines()
                # Truncate file so we don't need to close it and open it again
                # for writing
                file.seek(0)
                file.truncate()

                def write_line(key, val):
                    return key + "=" + val + "\n"

                # Loop through the file to change with new values in dict
                for line in lines:
                    if not line.startswith("#") and len(line) > 1:
                        (key, val) = line.rstrip('\n').split('=')
                        key = key.strip()
                        newVal = self.configOptions[key]

                        # Only update if the variable value has changed
                        if val != newVal:
                            line = write_line(key, newVal)
                        handled_keys.add(key)
                    file.write(line)
                for key in self.configOptions.keys():
                    if key not in handled_keys:
                        file.write(write_line(key, self.configOptions[key]))
        except IOError as e:
                print "ERROR opening file " + self.fileName + ": " + e.strerror + "\n"

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

    def get(self, key, default_value):
        try:
            return self[key]
        except Exception:
            return default_value
