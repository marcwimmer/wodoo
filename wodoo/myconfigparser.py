# used to read and write to settings
import os
from pathlib import Path
from .tools import atomic_write


def _get_ignore_case_item(d, k):
    try:
        return d[k]
    except KeyError:
        if isinstance(k, str):
            for i in d.keys():
                if i.lower() == k.lower():
                    return d[i]
            else:
                raise
        else:
            raise


class MyConfigParser:
    def __init__(self, fileName, debug=False):
        if isinstance(fileName, dict):
            self.fileName = None
            self.configOptions = fileName
        else:
            self.fileName = Path(fileName)
            self.configOptions = {}
            if self.fileName.exists():
                self._open()
        del fileName
        self.debug = debug

    def apply(self, other):
        for k in other.keys():
            self[k] = other[k]

    def clear(self):
        self.configOptions.clear()
        if self.fileName:
            self.fileName.parent.mkdir(exist_ok=True, parents=True)
            self.fileName.write_text("")

    def keys(self):
        return self.configOptions.keys()

    def _open(self):
        if not self.fileName or not self.fileName.exists():
            return
        content = self.fileName.read_text().strip()
        for line in content.split("\n"):
            # If it isn't a comment get the variable and value and put it on a dict
            if not line.startswith("#") and len(line) > 1:
                if "=" not in line:
                    import click

                    click.secho(
                        f"Invalid configuration option '{line}' ignored.",
                        fg="red",
                    )
                    continue
                (key, val) = line.rstrip("\n").split("=", 1)
                val = val.strip()
                val = val.strip('"')
                val = val.strip("'")
                self.configOptions[key.strip()] = val

    def write(self):
        handled_keys = set()
        if not self.fileName:
            return
        # Write the file contents
        if not self.fileName.is_file():
            self.fileName.parent.mkdir(exist_ok=True, parents=True)

        lines = []
        if self.fileName.exists():
            lines = self.fileName.read_text().splitlines()

        def format_line(key, val):
            if val is None:
                raise Exception("None value not allowed for: {}".format(key))
            return key + "=" + str(val)

        # Loop through the file to change with new values in dict
        def _update_lines():
            for line in lines:
                if line.startswith("#") or len(line) <= 1:
                    yield line
                    continue
                (key, val) = line.rstrip("\n").split("=", 1)
                key = key.strip()
                if key in self.configOptions:
                    newVal = self.configOptions[key]

                    # Only update if the variable value has changed
                line = format_line(key, newVal)
                yield line
                handled_keys.add(key)

            for key in self.configOptions.keys():
                if key not in handled_keys:
                    yield format_line(key, self.configOptions[key])

        with atomic_write(self.fileName) as file:
            file.write_text("\n".join(_update_lines()) + "\n")

    def __getitem__(self, key):
        for data in (self.configOptions, os.environ):
            try:
                return _get_ignore_case_item(data, key)
            except KeyError:
                if isinstance(key, int):
                    keys = data.keys()
                    return _get_ignore_case_item(data[keys[key]])
                else:
                    raise KeyError(
                        f"Key {key} doesn't exist in {self.fileName}"
                    )

    def __setitem__(self, key, value):
        if isinstance(value, list):
            value_list = "("
            for item in value:
                value_list += ' "' + item + '"'
            value_list += " )"
            self.configOptions[key] = value_list
        else:
            self.configOptions[key] = value

    def get(self, key, default_value=""):
        try:
            return self[key]
        except Exception:
            return default_value
