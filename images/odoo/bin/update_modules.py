#!/usr/bin/python3
import os
import datetime
import sys
import tempfile
import subprocess
from pathlib import Path
from time import sleep
import odoo_tools
from odoo_tools import odoo_config
from odoo_tools import odoo_parser
from odoo_tools.module_tools import get_all_langs
from odoo_tools.module_tools import delete_qweb
from odoo_tools.module_tools import Module, Modules, DBModules
from odoo_tools.odoo_config import customs_dir
from odoo_tools.odoo_config import MANIFEST
from odoo_tools.tools import __exists_table
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
NO_DANGLING_CHECK = [x for x in sys.argv[1:] if x.strip() == "no-dangling-check"]

def _get_uninstalled_modules_that_are_auto_install_and_should_be_installed():
    modules = []
    modules += DBModules.get_uninstalled_modules_that_are_auto_install_and_should_be_installed()
    return sorted(list(set(modules)))

def update(mode, modules):
    assert mode in ['i', 'u']
    assert modules
    assert isinstance(modules, list)

    if ','.join(modules) == 'all':
        raise Exception("update 'all' not allowed")

    if RUN_TESTS:
        if mode == "i":
            TESTS = '' # dont run tests at install
        else:
            TESTS = '--test-enable'
    else:
        TESTS = ''

    if not ONLY_I18N:
        print(mode, modules)
        # obj_module = Module.get_by_name(module)
        if mode == 'i':
            modules = [x for x in modules if not DBModules.is_module_installed(x)]
            if not modules:
                return
        params = [
            '-' + mode,
            ','.join(modules),
            '--stop-after-init',
        ]
        if TESTS:
            params += [TESTS]
        exec_odoo('config_update', *params)
        for module in modules:
            if not DBModules.is_module_installed(module):
                if mode == 'i':
                    print("{} is not installed - but it was tried to be installed.".format(module))
                else:
                    print("{} update error".format(module))
                sys.exit(1)
            del module

    if I18N_OVERWRITE or ONLY_I18N:
        for module in modules:
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
                            '--i18n-import={}/i18n/{}.po'.format(module.name, lang),
                            '--i18n-overwrite',
                            '--stop-after-init',
                        ]
                        exec_odoo('config_update', *params)
            del module

    print(mode, ','.join(modules), 'done')

def update_module_list():
    MOD = "update_module_list"
    if not DBModules.is_module_installed(MOD):
        print("Update Module List is not installed - installing it...")
        update('i', [MOD])
        return

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
    update('u', [MOD])


def _uninstall_marked_modules():
    """
    Checks for file "uninstall" in customs root and sets modules to uninstalled.
    """

    manifest = MANIFEST()
    modules = manifest.get('uninstall', [])
    for module in modules:
        print("Uninstalling marked module: {}".format(module))
        DBModules.uninstall_module(module, raise_error=False)


def main():
    MODULE = PARAMS[0] if PARAMS else ""
    MODULE = [x for x in MODULE.split(",") if x != 'all']
    single_module = len(MODULE) == 1
    if not MODULE:
        raise Exception("requires module!")

    _uninstall_marked_modules()

    if not NO_DANGLING_CHECK:
        dangling_modules = DBModules.get_dangling_modules()
        if any(x[1] == 'uninstallable' for x in dangling_modules):
            for x in dangling_modules:
                print("{}: {}".format(*x[:2]))
            if INTERACTIVE and input("Uninstallable modules found - shall I set them to 'uninstalled'? [y/N]").lower() == 'y':
                DBModules.set_uninstallable_uninstalled()

        if DBModules.get_dangling_modules():
            if INTERACTIVE and not NO_DANGLING_CHECK:
                DBModules.show_install_state(raise_error=False)
                input("Abort old upgrade and continue? (Ctrl+c to break)")
                DBModules.abort_upgrade()
            else:
                DBModules.abort_upgrade()

    print("--------------------------------------------------------------------------")
    print("Updating Module {}".format(MODULE))
    print("--------------------------------------------------------------------------")

    summary = []

    for module in list(MODULE):
        if not DBModules.is_module_installed(module):
            if not DBModules.is_module_listed(module):
                update_module_list()
                if not DBModules.is_module_listed(module):
                    raise Exception("After updating module list, module was not found: {}".format(module))
            update('i', [module])
            MODULE = [x for x in MODULE if x != module]
            summary.append("INSTALL " + module)

    if DELETE_QWEB:
        for module in MODULE:
            print("Deleting qweb of module {}".format(module))
            delete_qweb(module)

    if MODULE:
        update('u', MODULE)
    for module in MODULE:
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
            update('i', auto_install_modules)

    print("--------------------------------------------------------------------------------")
    print("Summary of update module")
    print("--------------------------------------------------------------------------------")
    for line in summary:
        print(line)

    if not single_module:
        DBModules.check_if_all_modules_from_install_are_installed()


if __name__ == '__main__':
    main()
