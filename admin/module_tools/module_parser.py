import os
from odoo_config import odoo_root
from consts import MANIFESTS
from odoo_parser import update_cache

class Field(object):
    pass

class Configuration(object):
    pass

class Model(object):
    pass

class Module(object):
    def __init__(self, root, plainfile):
        """
        Iterates over odoo module and gathers fields, tables, configs.

        root: the path to the module eg /opt/odoo/active_customs/modules/mod1
        plainfile: path to the file, containing the results of update_cache
        """
        assert any(os.path.isfile(os.path.join(root, m)) for m in MANIFESTS), 'not a module without manifest!'

        with open(plainfile, 'r') as f:
            content = f.read()
            lines = [x for x in content.split("\n") if '/{}/'.format(module_name) in x]

        self.models = []



if __name__ == '__main__':
    plainfile = update_cache()
    mod = Module(os.path.join(odoo_root(), 'modules/heine_hdmr'))
