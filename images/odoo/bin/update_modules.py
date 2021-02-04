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
from odoo_tools.module_tools import delete_qweb as do_delete_qweb
from odoo_tools.module_tools import Module, Modules, DBModules
from odoo_tools.odoo_config import customs_dir
from odoo_tools.odoo_config import MANIFEST
from tools import prepare_run
from tools import exec_odoo

mode_text = {
    'i': 'installing',
    'u': 'updating',
}

class Config(object):
    pass


pass_config = click.make_pass_decorator(Config, ensure=True)

def update(config, mode, modules):
    assert mode in ['i', 'u']
    assert isinstance(modules, list)
    if not modules:
        return

    # if ','.join(modules) == 'all': # needed for migration
    #    raise Exception("update 'all' not allowed")

    if config.run_test:
        if mode == "i":
            TESTS = '' # dont run tests at install, automatically run (says docu)
        else:
            TESTS = '--test-enable'
    else:
        TESTS = ''

    if not config.only_i18n:
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
            if module != 'all':
                if not DBModules.is_module_installed(module):
                    if mode == 'i':
                        click.secho("{} is not installed - but it was tried to be installed.".format(module), fg='red')
                    else:
                        click.secho("{} update error".format(module), fg='red')
            del module
        rc and sys.exit(rc)

    if config.i18n_overwrite or config.only_i18n:
        for module in modules:
            module = Module.get_by_name(module)
            if DBModules.is_module_installed(module.name):
                for lang in get_all_langs():
                    if lang == 'en_US':
                        continue
                    import pudb
                    pudb.set_trace()
                    lang_file = module.get_lang_file(lang)
                    if not lang_file:
                        lang_file = module.get_lang_file(lang.split("_")[0])
                    if not lang_file:
                        continue
                    if lang_file.exists():
                        print(f"Updating language {lang} for module {module}:")
                        params = [
                            '-l',
                            lang,
                            f'--i18n-import={module.path}/i18n/{lang_file.name}',
                            '--i18n-overwrite',
                            '--stop-after-init',
                        ]
                        rc = exec_odoo('config_update', *params)
                        if rc:
                            click.secho(f"Error at updating translations at {module} {lang}", fg='red')
                        rc and sys.exit(rc)
            del module

    print(mode, ','.join(modules), 'done')


def _install_module(config, modname):
    if not DBModules.is_module_listed(modname):
        if modname not in ['update_module_list']:
            update_module_list()
    if not DBModules.is_module_installed(modname):
        print("Update Module List is not installed - installing it...")
        update(config, 'i', [modname])
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
    update(config, 'u', [modname])


def update_module_list(config):
    if config.no_update_modulelist:
        click.secho("No update module list flag set. Not updating.")
        return
    _install_module(config, "update_module_list")


def _uninstall_marked_modules(config):
    """
    Checks for file "uninstall" in customs root and sets modules to uninstalled.
    """
    if os.getenv("USE_DOCKER", "1") == "0":
        return
    if config.odoo_version < 11.0:
        return
    module = 'server_tools_uninstaller'
    try:
        DBModules.is_module_installed(module, raise_exception_not_initialized=True)
    except UserWarning:
        click.secho("Nothing to uninstall - db not initialized yet.", fg='yellow')
        return
    else:
        # check if something is todo
        to_uninstall = config.manifest.get('uninstall', [])
        to_uninstall = [x for x in to_uninstall if DBModules.is_module_installed(x)]
        if to_uninstall:
            click.secho("Going to uninstall {}".format(', '.join(to_uninstall)), fg='red')
            _install_module(config, module)


def _get_to_install_modules(config, modules):
    for module in modules:
        if module in ['all']:
            continue

        if not DBModules.is_module_installed(module, raise_exception_not_initialized=(module not in ('base',))):
            if not DBModules.is_module_listed(module):
                if module != 'base':
                    update_module_list(config)
                    if not DBModules.is_module_listed(module):
                        if not config.no_update_modulelist:
                            raise Exception(f"After updating module list, module was not found: {module}")
                        else:
                            raise Exception(f"Module not found to update: {module}")
            yield module


def dangling_check(config):
    dangling_modules = DBModules.get_dangling_modules()
    if any(x[1] == 'uninstallable' for x in dangling_modules):
        for x in dangling_modules:
            print("{}: {}".format(*x[:2]))
        if config.interactive and input("Uninstallable modules found - shall I set them to 'uninstalled'? [y/N]").lower() == 'y':
            DBModules.set_uninstallable_uninstalled()

    if DBModules.get_dangling_modules():
        if config.interactive:
            DBModules.show_install_state(raise_error=False)
            input("Abort old upgrade and continue? (Ctrl+c to break)")
            DBModules.abort_upgrade()
        else:
            DBModules.abort_upgrade()


@click.group(invoke_without_command=True)
def cli():
    pass

@click.command()
@click.argument("modules", required=False)
@click.option('--non-interactive', is_flag=True)
@click.option('--no-update-modulelist', is_flag=True)
@click.option('--i18n', is_flag=True, help="Overwrite I18N")
@click.option('--only-i18n', is_flag=True)
@click.option('--delete-qweb', is_flag=True)
@click.option('--no-tests', is_flag=True)
@click.option('--no-dangling-check', is_flag=True)
@click.option('--no-install-server-wide-first', is_flag=True)
@click.option('--no-extra-addons-paths', is_flag=True)
@pass_config
def main(config, modules, non_interactive, no_update_modulelist, i18n, only_i18n, delete_qweb, no_tests, no_dangling_check, no_install_server_wide_first, no_extra_addons_paths):

    config.interactive = not non_interactive
    config.i18n_overwrite = i18n
    config.odoo_version = float(os.getenv("ODOO_VERSION"))
    config.only_i18n = only_i18n
    config.no_extra_addons_paths = no_extra_addons_paths

    config.run_test = os.getenv("ODOO_RUN_TESTS", "1") == "1"
    if no_tests:
        config.run_test = False

    config.no_update_modulelist = no_update_modulelist
    config.manifest = MANIFEST()
    prepare_run(config)

    modules = list(filter(bool, modules.split(",")))
    summary = defaultdict(list)
    single_module = len(modules) == 1
    if not modules:
        raise Exception("requires module!")

    if not no_dangling_check:
        dangling_check(config)
    to_install_modules = list(_get_to_install_modules(config, modules))

    # install server wide modules and/or update them
    if not no_install_server_wide_first and not modules or tuple(modules) == ('all',):
        c = 'magenta'
        server_wide_modules = config.manifest['server-wide-modules']
        # leave out base modules
        server_wide_modules = list(filter(lambda x: x not in ['web'], server_wide_modules))
        click.secho("--------------------------------------------------------------------------", fg=c)
        click.secho(f"Installing/Updating Server wide modules {','.join(server_wide_modules)}", fg=c)
        click.secho("--------------------------------------------------------------------------", fg=c)
        to_install_swm = list(filter(lambda x: x in to_install_modules, server_wide_modules))
        to_update_swm = list(filter(lambda x: x not in to_install_swm, server_wide_modules))
        click.secho(f"Installing {','.join(to_install_swm)}", fg=c)
        update(config, 'i', to_install_swm)
        click.secho(f"Updating {','.join(to_install_swm)}", fg=c)
        update(config, 'u', to_update_swm)

        _uninstall_marked_modules(config)

    c = 'yellow'
    click.secho("--------------------------------------------------------------------------", fg=c)
    click.secho(f"Updating Module {','.join(modules)}", fg=c)
    click.secho("--------------------------------------------------------------------------", fg=c)

    update(config, 'i', to_install_modules)
    summary['installed'] += to_install_modules
    modules = list(filter(lambda x: x not in summary['installed'], modules))

    # if delete_qweb:
        # for module in modules:
            # print("Deleting qweb of module {}".format(module))
            # do_delete_qweb(module)

    if modules:
        update(config, 'u', modules)
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
