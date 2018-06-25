#!/usr/bin/python
import os
import datetime
import sys
import tempfile
import subprocess
from time import sleep
sys.path.append("/opt/odoo/admin/module_tools")
sys.path.append("/")
import module_tools
from utils import get_env

PARAMS = [x for x in sys.argv[1:] if x not in ['-fast']]
FASTMODE = any(x =='-fast' for x in sys.argv)
DANGLING = False

def get_modules():
    modules = []
    modules += module_tools.get_customs_modules("/opt/odoo/active_customs", "to_update")
    return sorted(list(set(modules)))

def get_uninstalled_modules_that_are_auto_install_and_should_be_installed():
    modules = []
    modules += module_tools.get_uninstalled_modules_that_are_auto_install_and_should_be_installed()
    return sorted(list(set(modules)))

def delete_qweb(module):
    # for odoo delete all qweb views and take the new ones;
    module_tools.delete_qweb(module)

def is_module_installed(module):
    if not module:
        return False
    return module_tools.is_module_installed(module)

def update(mode, module):
    assert mode in ['i', 'u']
    assert module
    assert isinstance(module, (str, unicode))

    if module == 'all':
        raise Exception("update 'all' not allowed")

    if os.getenv("ODOO_MODULE_UPDATE_RUN_TESTS") == "1":
        if mode == "i":
            TESTS = '' # dont run tests at install
        else:
            TESTS = '--test-enable'
    else:
        TESTS = ''

    params = [
        '/usr/bin/sudo',
        '-H',
        '-u',
        os.getenv("ODOO_USER"),
        os.path.expandvars("$SERVER_DIR/{}".format(get_env()["ODOO_EXECUTABLE"])),
        '-c',
        os.path.expandvars("$CONFIG_DIR/config_openerp"),
        '-d',
        os.path.expandvars("$DBNAME"),
        '-' + mode,
        module,
        '--stop-after-init',
        '--log-level=debug',
    ]
    if TESTS:
        params += [TESTS]
    proc = subprocess.Popen(params)
    proc.wait()
    print mode, module, 'done'

def update_module_list():
    MOD = "update_module_list"
    if is_module_installed(MOD):
        print "Update Module List is not installed - installing it..."
        update('i', MOD)

    if not is_module_installed(MOD):
        print("")
        print("")
        print("")
        print("Severe update error - module 'update_module_list' not installable, but is required.")
        print("")
        print("Try to manually start odoo and click on 'Module Update' and install this by hand.")
        print("")
        print("")
        sys.exit(82)
    update('u', MOD)


def check_for_dangling_modules():
    dangling = module_tools.dangling_modules()
    print dangling

def main():
    MODULE = PARAMS[0] if PARAMS else ""

    print("--------------------------------------------------------------------------")
    print("Updating Module {}".format(MODULE))
    print("--------------------------------------------------------------------------")

    if MODULE == 'all':
        MODULE = ''

    subprocess.check_call([
        'bash',
        '-c',
        'source /eval_odoo_settings.sh; /apply-env-to-config.sh'
    ])

    summary = []
    # could be, that a new version is triggered
    if not FASTMODE:
        check_for_dangling_modules()

    if not FASTMODE and not DANGLING:
        update_module_list()

    if not MODULE:
        MODULE = ','.join(get_modules() + module_tools.get_uninstalled_modules_where_others_depend_on())

    for module in MODULE.split(','):
        if not is_module_installed(module):
            update('i', module)
            summary.append("INSTALL " + module)

    if os.getenv("DEVMODE", "") == "1":
        for module in MODULE.split(','):
            delete_qweb(module)
    update('u', module)
    for module in module.split(","):
        summary.append("UPDATE " + module)

    # check if at auto installed modules all predecessors are now installed; then install them
    if not FASTMODE:
        auto_install_modules = ','.join(get_uninstalled_modules_that_are_auto_install_and_should_be_installed())
        if auto_install_modules:
            print("Going to install following modules, that are auto installable modules")
            sleep(5)
            print ','.join(auto_install_modules)
            print("")
            sleep(2)
            print("You should press Ctrl+C NOW to abort")
            sleep(8)
            update('i', auto_install_modules)

    print("--------------------------------------------------------------------------------")
    print("Summary of update module")
    print("--------------------------------------------------------------------------------")
    for line in summary:
        print line
    print("UPDATE {}".format(MODULE))

    if not FASTMODE:
        module_tools.check_if_all_modules_from_instal_are_installed()


if __name__ == '__main__':
    main()
