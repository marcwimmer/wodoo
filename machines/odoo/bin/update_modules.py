#!/usr/bin/python3
import os
import datetime
import sys
import tempfile
import subprocess
from pathlib import Path
from time import sleep
from module_tools import odoo_config
from module_tools import odoo_parser
from module_tools.module_tools import get_all_langs
from module_tools.module_tools import delete_qweb
from module_tools.module_tools import Module, Modules, DBModules
from module_tools.odoo_config import customs_dir
from tools import prepare_run
from tools import exec_odoo
prepare_run()

INTERACTIVE = not any(x == '--non-interactive' for x in sys.argv)
NO_UPDATE_MODULELIST = any(x == '--no-update-modulelist' for x in sys.argv)
PARAMS = [x for x in sys.argv[1:] if not x.startswith("-")]
I18N_OVERWRITE = [x for x in sys.argv[1:] if x.strip().startswith("--i18n")]
ONLY_I18N = [x for x in sys.argv[1:] if x.strip().startswith("--only-i18n")]
DELETE_QWEB = [x for x in sys.argv[1:] if x.strip().startswith("--delete-qweb")]
RUN_TESTS = [x for x in sys.argv[1:] if x.strip().startswith("--run-tests")]

def _get_uninstalled_modules_that_are_auto_install_and_should_be_installed():
    modules = []
    modules += DBModules.get_uninstalled_modules_that_are_auto_install_and_should_be_installed()
    return sorted(list(set(modules)))

def update(mode, module):
    assert mode in ['i', 'u']
    assert module
    assert isinstance(module, str)

    if module == 'all':
        raise Exception("update 'all' not allowed")

    if RUN_TESTS:
        if mode == "i":
            TESTS = '' # dont run tests at install
        else:
            TESTS = '--test-enable'
    else:
        TESTS = ''

    if not ONLY_I18N:
        print(mode, module)
        # obj_module = Module.get_by_name(module)
        params = [
            '-' + mode,
            module,
            '--stop-after-init',
            '--log-level=debug',
        ]
        if TESTS:
            params += [TESTS]
        exec_odoo('config_update', *params, force_no_gevent=True)
        if not DBModules.is_module_installed(module):
            if mode == 'i':
                print("{} is not installed - but it was tried to be installed.".format(module))
            else:
                print("{} update error".format(module))
            sys.exit(1)

    if I18N_OVERWRITE or ONLY_I18N:
        for module in module.split(','):
            module = Module.get_by_name(module)
            if DBModules.is_module_installed(module.name):
                for lang in get_all_langs():
                    if lang == 'en_US':
                        continue
                    lang_file = module.get_lang_file(lang)
                    if not lang_file:
                        continue
                    if lang_file.exists():
                        print("Updating language {} for module {}:".format(lang, module))
                        params = [
                            '-l',
                            lang,
                            '--i18n-import={}/i18n/{}.po'.format(module, lang),
                            '--i18n-overwrite',
                        ]
                        exec_odoo('config_update', *params, force_no_gevent=True)

    print(mode, module, 'done')

def update_module_list():
    MOD = "update_module_list"
    if not DBModules.is_module_installed(MOD):
        print("Update Module List is not installed - installing it...")
        update('i', MOD)

    if not DBModules.is_module_installed(MOD):
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


def _uninstall_marked_modules():
    """
    Checks for file "uninstall" in customs root and sets modules to uninstalled.
    """
    file = (Path(customs_dir()) / 'uninstall')
    if not file.exists():
        return
    modules = filter(lambda x: x.strip(), file.open().read().split("\n"))
    for module in modules:
        DBModules.uninstall_module(module, raise_error=False)

def main():
    MODULE = PARAMS[0] if PARAMS else ""
    single_module = MODULE and ',' not in MODULE

    _uninstall_marked_modules()

    print("--------------------------------------------------------------------------")
    print("Updating Module {}".format(MODULE))
    print("--------------------------------------------------------------------------")

    if MODULE == 'all':
        MODULE = ''

    if not MODULE:
        raise Exception("requires module!")

    summary = []

    for module in MODULE.split(','):
        if not DBModules.is_module_installed(module):
            if not DBModules.is_module_listed(module):
                update_module_list()
                if not DBModules.is_module_listed(module):
                    raise Exception("After updating module list, module was not found: {}".format(module))
            update('i', module)
            summary.append("INSTALL " + module)

    if DELETE_QWEB:
        for module in MODULE.split(','):
            print("Deleting qweb of module {}".format(module))
            delete_qweb(module)
    update('u', MODULE)
    for module in MODULE.split(","):
        summary.append("UPDATE " + module)

    # check if at auto installed modules all predecessors are now installed; then install them
    if not single_module:
        auto_install_modules = _get_uninstalled_modules_that_are_auto_install_and_should_be_installed()
        if auto_install_modules:
            print("Going to install following modules, that are auto installable modules")
            print(','.join(auto_install_modules))
            print("")
            if INTERACTIVE:
                input("You should press Ctrl+C NOW to abort")
            update('i', ','.join(auto_install_modules))

    print("--------------------------------------------------------------------------------")
    print("Summary of update module")
    print("--------------------------------------------------------------------------------")
    for line in summary:
        print(line)

    if not single_module:
        DBModules.check_if_all_modules_from_install_are_installed()


if __name__ == '__main__':
    main()
