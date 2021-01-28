#!/usr/bin/env python3
from collections import defaultdict
import click
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
from tools import prepare_run
from tools import exec_odoo
prepare_run()

INTERACTIVE = not any(x == '--non-interactive' for x in sys.argv)
NO_UPDATE_MODULELIST = any(x == '--no-update-modulelist' for x in sys.argv)
PARAMS = [x for x in sys.argv[1:] if not x.startswith("-")]
I18N_OVERWRITE = [x for x in sys.argv[1:] if x.strip().startswith("--i18n")]
ONLY_I18N = [x for x in sys.argv[1:] if x.strip().startswith("--only-i18n")]
DELETE_QWEB = [x for x in sys.argv[1:] if x.strip().startswith("--delete-qweb")]
NO_RUN_TESTS = [x for x in sys.argv[1:] if x.strip().startswith("--no-tests")]
NO_DANGLING_CHECK = [x for x in sys.argv[1:] if x.strip() == "no-dangling-check"]

ODOO_VERSION = float(os.getenv("ODOO_VERSION"))

run_test = os.getenv("ODOO_RUN_TESTS", "1") == "1"
if NO_RUN_TESTS:
    run_test = False

manifest = MANIFEST()

mode_text = {
    'i': 'installing',
    'u': 'updating',
}

def update(mode, modules):
    assert mode in ['i', 'u']
    assert isinstance(modules, list)
    if not modules:
        return

    if ','.join(modules) == 'all':
        raise Exception("update 'all' not allowed")

    if run_test:
        if mode == "i":
            TESTS = '' # dont run tests at install, automatically run (says docu)
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
        rc = exec_odoo('config_update', *params)
        if rc:
            click.secho(f"Error at {mode_text[mode]} of: {','.join(modules)}", fg='red', bold=True)
        for module in modules:
            if not DBModules.is_module_installed(module):
                if mode == 'i':
                    click.secho("{} is not installed - but it was tried to be installed.".format(module), fg='red')
                else:
                    click.secho("{} update error".format(module), fg='red')
            del module
        rc and sys.exit(rc)

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
                        print(f"Updating language {lang} for module {module}:")
                        params = [
                            '-l',
                            lang,
                            f'--i18n-import={module.path}/i18n/{lang}.po',
                            '--i18n-overwrite',
                            '--stop-after-init',
                        ]
                        rc = exec_odoo('config_update', *params)
                        if rc:
                            click.secho(f"Error at updating translations at {module} {lang}", fg='red')
                        rc and sys.exit(rc)
            del module

    print(mode, ','.join(modules), 'done')

def _install_module(modname):
    if not DBModules.is_module_listed(modname):
        if modname not in ['update_module_list']:
            update_module_list()
    if not DBModules.is_module_installed(modname):
        print("Update Module List is not installed - installing it...")
        update('i', [modname])
        return

    if not DBModules.is_module_installed(modname):
        print("")
        print("")
        print("")
        print("Severe update error - module 'update_module_list' not installable, but is required.")
        print("")
        print("Try to manually start odoo and click on 'Module Update' and install this by hand.")
        print("")
        print("")
        sys.exit(82)
    update('u', [modname])

def update_module_list():
    _install_module("update_module_list")

def _uninstall_marked_modules():
    """
    Checks for file "uninstall" in customs root and sets modules to uninstalled.
    """
    if os.getenv("USE_DOCKER", "1") == "0":
        return
    if ODOO_VERSION < 11.0:
        return
    module = 'server_tools_uninstaller'
    try:
        DBModules.is_module_installed(module, raise_exception_not_initialized=True)
    except UserWarning:
        click.secho("Nothing to uninstall - db not initialized yet.", fg='yellow')
        return
    else:
        # check if something is todo
        to_uninstall = manifest.get('uninstall', [])
        to_uninstall = [x for x in to_uninstall if DBModules.is_module_installed(x)]
        if to_uninstall:
            click.secho("Going to uninstall {}".format(', '.join(to_uninstall)), fg='red')
            _install_module(module)

def _get_to_install_modules(modules):
    for module in modules:
        if not DBModules.is_module_installed(module, raise_exception_not_initialized=(module != 'base')):
            if not DBModules.is_module_listed(module):
                if module != 'base':
                    update_module_list()
                    if not DBModules.is_module_listed(module):
                        raise Exception("After updating module list, module was not found: {}".format(module))
            yield module

def install_new_modules(modules, summary):
    update('i', modules)

def dangling_check():
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

def main():
    modules = PARAMS[0] if PARAMS else ""
    modules = [x for x in modules.split(",") if x != 'all']
    single_module = len(modules) == 1
    if not modules:
        raise Exception("requires module!")

    dangling_check()
    to_install_modules = list(_get_to_install_modules(list(modules)))

    # install server wide modules and/or update them
    c = 'magenta'
    server_wide_modules = manifest['server-wide-modules']
    click.secho("--------------------------------------------------------------------------", fg=c)
    click.secho(f"Installing/Updating Server wide modules {','.join(server_wide_modules)}", fg=c)
    click.secho("--------------------------------------------------------------------------", fg=c)
    to_install_swm = list(filter(lambda x: x in to_install_modules, server_wide_modules))
    to_update_swm = list(filter(lambda x: x not in to_install_swm, server_wide_modules))
    click.secho(f"Installing {','.join(to_install_swm)}", fg=c)
    update('i', to_install_swm)
    click.secho(f"Updating {','.join(to_install_swm)}", fg=c)
    update('u', to_update_swm)

    _uninstall_marked_modules()

    c = 'yellow'
    click.secho("--------------------------------------------------------------------------", fg=c)
    click.secho(f"Updating Module {','.join(modules)}", fg=c)
    click.secho("--------------------------------------------------------------------------", fg=c)

    summary = defaultdict(list)
    _uninstall_marked_modules()

    install_new_modules(
        to_install_modules,
    )
    summary['installed'] += to_install_modules
    modules = list(filter(lambda x: x not in summary['installed'], modules))

    if DELETE_QWEB:
        for module in modules:
            print("Deleting qweb of module {}".format(module))
            delete_qweb(module)

    if modules:
        update('u', modules)
        summary['update'] += modules

    c = 'green'
    click.secho("================================================================================", fg=c)
    click.secho(f"Summary of update module", fg=c)
    click.secho("--------------------------------------------------------------------------------", fg=c)
    for key, value in summary.items():
        click.secho(f'{key}: {",".join(value)}', fg=c)

    click.secho("================================================================================", fg=c)

    if not single_module:
        DBModules.check_if_all_modules_from_install_are_installed()


if __name__ == '__main__':
    main()
