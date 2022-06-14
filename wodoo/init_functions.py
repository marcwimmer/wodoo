from collections import ChainMap
import sys
import importlib
import os
from pathlib import Path
from .myconfigparser import MyConfigParser  # NOQA

try:
    import click
except ImportError:
    click = None


def get_use_docker(files):
    try:
        myconfig = MyConfigParser(files["settings"])
    except Exception:
        USE_DOCKER = True
    else:
        USE_DOCKER = myconfig.get("USE_DOCKER", "1") == "1"

    return USE_DOCKER


def load_dynamic_modules(parent_dir):
    for module in parent_dir.glob("*/__commands.py"):
        if module.is_dir():
            continue
        spec = importlib.util.spec_from_file_location(
            "dynamic_loaded_module",
            str(module),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)


def _search_path(filename):
    filename = Path(filename)
    filename = filename.name
    paths = os.getenv("PATH", "").split(":")

    # add probable pyenv path also:
    execparent = Path(sys.executable).parent
    if execparent.name in ["bin", "sbin"]:
        paths = [execparent] + paths

    for path in paths:
        path = Path(path)
        if (path / filename).exists():
            return str(path / filename)


def _get_customs_root(p):
    # arg_dir = p
    if p:
        while len(p.parts) > 1:
            if (p / "MANIFEST").exists():
                return p
            p = p.parent


def make_absolute_paths(config, dirs, files, commands):
    from .consts import default_dirs, default_files, default_commands

    for (input, output) in [
        (default_dirs, dirs),
        (default_files, files),
        (default_commands, commands),
    ]:
        output.clear()
        for k, v in input.items():
            output[k] = v

    dirs["odoo_home"] = Path(os.environ["ODOO_HOME"])

    def replace_keys(value, key_values):
        for k, v in key_values.items():
            p = ["${" + k + "}", f"${k}"]
            for p in p:
                if p in str(value):
                    value = value.replace(p, str(v))
        return value

    def make_absolute(d, key_values={}):
        for k, v in list(d.items()):
            if not v:
                continue
            skip = False
            v = replace_keys(v, key_values)

            for value, name in [
                (config.HOST_RUN_DIR, "${run}"),
                (config.WORKING_DIR, "${working_dir}"),
                (config.project_name, "${project_name}"),
            ]:
                if name in str(v):
                    if value:
                        v = str(v).replace(name, str(value))
                    else:
                        del d[k]
                        skip = True
                        break
            if skip:
                continue
            if str(v).startswith("~"):
                v = Path(os.path.expanduser(str(v)))

            if not str(v).startswith("/"):
                v = dirs["odoo_home"] / v
            d[k] = Path(v)

    make_absolute(dirs)
    make_absolute(files, dirs)

    for k in commands:
        commands[k] = [
            replace_keys(x, ChainMap(config.__dict__, files, dirs)) for x in commands[k]
        ]
