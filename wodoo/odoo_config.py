from contextlib import contextmanager
from collections import Counter
import shutil
import tempfile


try:
    import arrow
except Exception:
    arrow = None
from collections import OrderedDict
from . import click
import json
from pathlib import Path
import os
from .tools import abort

try:
    import psycopg2
except Exception:
    pass


def get_odoo_addons_paths(
    relative=False, no_extra_addons_paths=False, additional_addons_paths=False
):
    m = MANIFEST()
    c = customs_dir()
    res = []
    addons_paths = m["addons_paths"]
    if additional_addons_paths:
        addons_paths += additional_addons_paths

    if current_version() <= 9.0:
        MUST = ["odoo/openerp/addons", "odoo/addons"]
    else:
        MUST = ["odoo/odoo/addons", "odoo/addons"]
    for must in reversed(MUST):
        if must in addons_paths:
            continue
        addons_paths.insert(0, must)

    for x in addons_paths:
        if no_extra_addons_paths:
            if x not in MUST:
                continue
        if relative:
            res.append(x)
        else:
            res.append(c / x)

    return res


def customs_dir():
    env_customs_dir = os.getenv("CUSTOMS_DIR") or os.getenv("HOST_CUSTOMS_DIR")
    if not env_customs_dir:
        manifest_file = Path(os.getcwd()) / "MANIFEST"
        if manifest_file.exists():
            return manifest_file.parent
        else:
            here = Path(os.getcwd())
            while not (here / "MANIFEST").exists():
                here = here.parent
                if here.parent == here:
                    break
            if (here / "MANIFEST").exists():
                return here

            click.secho("no MANIFEST file found in current directory.")
    if not env_customs_dir:
        return None
    return Path(env_customs_dir)


def plaintextfile():
    path = customs_dir() / ".odoo.ast"
    return path


def _read_file(path, default=None):
    try:
        with open(path, "r") as f:
            return (f.read() or "").strip()
    except Exception:
        return default


def MANIFEST_FILE():
    _customs_dir = customs_dir()
    if not _customs_dir:
        return None
    return _customs_dir.resolve().absolute() / "MANIFEST"


class MANIFEST_CLASS(object):
    def __init__(self):
        self.path = MANIFEST_FILE()

        self._apply_defaults()

    def _apply_defaults(self):
        d = self._get_data()
        d.setdefault("modules", [])
        # patches ?

        self.patch_dir = customs_dir() / "patches"

        if "version" not in d:
            self["version"] = float(d["version"])

    def _get_data(self):
        content = self.path.read_text() or "{}"
        try:
            return OrderedDict(eval(content))
        except:
            abort(f"Could not parse {content}")

    def __getitem__(self, key):
        data = self._get_data()
        return data[key]

    def get(self, key, default):
        return self._get_data().get(key, default)

    def __setitem__(self, key, value):
        data = self._get_data()
        data[key] = value
        self._update(data)

    def _update(self, d):
        d["install"] = list(sorted(set(d["install"])))
        s = json.dumps(d, indent=4)
        tfile = Path(tempfile.mktemp(suffix=".MANIFEST"))
        tfile.write_text(s)
        shutil.move(tfile, MANIFEST_FILE())

        if len(set(d["addons_paths"])) != len(d["addons_paths"]):
            duplicates = [
                item
                for item, count in Counter(d["addons_paths"]).items()
                if count > 1
            ]
            abort(f"Addons Paths contains duplicate entries: {duplicates}")

    def rewrite(self):
        self._update(self._get_data())


def MANIFEST():
    return MANIFEST_CLASS()


cache_version = {}


def current_version():
    if cache_version.get("value") is None:
        cache_version["value"] = float(MANIFEST()["version"])
    return cache_version["value"]


def get_postgres_connection_params(inside_container=None):
    config = get_settings()
    if (
        not inside_container
        and os.getenv("DOCKER_MACHINE") != "1"
        and config.get("RUN_POSTGRES") == "1"
    ):
        host = Path(os.environ["HOST_RUN_DIR"]) / "postgres.socket"
        port = 0

    else:
        host = config["DB_HOST"]
        port = int(config.get("DB_PORT", "5432"))
    password = config["DB_PWD"]
    user = config["DB_USER"]
    return host, port, user, password


def get_settings():
    """
    Can run outside of host and inside host. Returns all values from
    composed settings file.
    """
    from .myconfigparser import MyConfigParser  # NOQA

    if os.getenv("DOCKER_MACHINE") == "1":
        settings_path = Path("/tmp/settings")
        content = ""
        for k, v in os.environ.items():
            v = v.replace("\n", " ")
            content += f"{k}={v}\n"
        settings_path.write_text(content)
    else:
        settings_path = Path(os.environ["HOST_RUN_DIR"]) / "settings"
    myconfig = MyConfigParser(settings_path)
    return myconfig


def get_conn(db=None, host=None):
    config = get_settings()
    if db != "postgres":
        # waiting until postgres is up
        get_conn(db="postgres")

    host, port, user, password = get_postgres_connection_params()
    db = db or config["DBNAME"]
    connstring = "dbname={}".format(db)

    for combi in [
        ("password", password),
        ("host", host),
        ("port", port),
        ("user", user),
    ]:
        if combi[1]:
            connstring += " {}='{}'".format(combi[0], combi[1])

    conn = psycopg2.connect(connstring)
    cr = conn.cursor()
    return conn, cr


@contextmanager
def get_conn_autoclose(*args, **kwargs):
    conn, cr = get_conn(*args, **kwargs)
    try:
        yield cr
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        cr.close()
        conn.close()


def translate_path_into_machine_path(path):
    path = customs_dir() / translate_path_relative_to_customs_root(path)
    return path


def translate_path_relative_to_customs_root(path):
    """
    The customs must contain a significant file named
    MANIFEST to indicate the root of the customs
    """

    cmf = MANIFEST_FILE().absolute().resolve().absolute()
    if not str(path).startswith("/"):
        return path

    try:
        path = path.resolve()
    except Exception:
        pass

    return path.relative_to(cmf.parent)


def manifest_file_names():
    result = "__manifest__.py"
    try:
        current_version()
    except Exception:
        pass
    else:
        if current_version() <= 10.0:
            result = "__openerp__.py"
        else:
            result = "__manifest__.py"
    return result
