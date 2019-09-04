import stat
import os
import platform
from pathlib import Path
import inspect

def after_compose(config):
    if platform.system() == "Linux":
        pass
    elif platform.system() in ["Darwin", "Windows"]:
        dir = Path(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))))
        template = (dir / 'unison.template.py').read_text()
        run_unison = Path(os.environ['HOME']) / '.odoo' / 'run' / 'run_unison.sh'
        run_unison.parent.mkdir(exist_ok=True)
        run_unison.write_text(template)
        run_unison.chmod(run_unison.stat().st_mode | stat.S_IEXEC)
        config["UNISON_ODOO_SRC_EXE"] = str(run_unison)
        config.write()

        _setup_unison_config(config)

def _setup_unison_config(config):
    """
    Usually source files are synced to local docker instances;
    but could also be synced to a remote machine.
    """
    default_conf = Path(os.environ['ODOO_HOME']) / 'images' / 'fssync' / 'odoo_source.prf'

    conf = default_conf.read_text()
    conf = conf.replace("__SOURCE__", os.environ["CUSTOMS_DIR"])
    conf = conf.replace("__HOST__", config["FSSYNC_HOST"])

    if platform.system() == 'Darwin':
        prf_file = Path(os.environ['HOME']) / "Library/Application Support/Unison/unison_odoo_src.prf"
    else:
        raise NotImplementedError()
    prf_file.write_text(conf)
