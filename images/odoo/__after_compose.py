import sys
import re
import base64
import click
import yaml
import inspect
import os
dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

MINIMAL_MODULES = ['anonymize'] # to include its dependencies

def _setup_remote_debugging(config, yml):
    if config.devmode:
        key = 'odoo'
    else:
        key = 'odoo_debug'
    yml['services'][key].setdefault('ports', [])
    if config.ODOO_PYTHON_DEBUG_PORT:
        yml['services'][key]['ports'].append(f"0.0.0.0:{config.ODOO_PYTHON_DEBUG_PORT}:5678")

def after_compose(config, settings, yml, globals):
    # store also in clear text the requirements
    from odoo_tools.tools import get_services
    from pathlib import Path

    yml['services'].pop('odoo_base')
    dirs = config.dirs
    # odoodc = yaml.safe_load((dirs['odoo_home'] / 'images/odoo/docker-compose.yml').read_text())

    odoo_machines = get_services(config, 'odoo_base', yml=yml)

    # download python3.x version
    python_tgz = Path(dir) / 'python' / f"Python-{settings['ODOO_PYTHON_VERSION']}.tgz"
    if not python_tgz.exists():
        PYVERSION = settings['ODOO_PYTHON_VERSION']
        click.secho(f"Execute:\nwget https://www.python.org/ftp/python/{PYVERSION}/Python-{PYVERSION}.tgz -P {python_tgz.parent}", fg='red')
        sys.exit(-1)

    PYTHON_VERSION = tuple([int(x) for x in config.ODOO_PYTHON_VERSION.split(".")])

    # Add remote debugging possibility in devmode
    _setup_remote_debugging(config, yml)

    if float(config.ODOO_VERSION) >= 13.0:
        # fetch dependencies from odoo lib requirements
        # requirements from odoo framework
        lib_python_dependencies = (dirs['odoo_home'] / 'requirements.txt').read_text().split("\n")

        # fetch the external python dependencies
        external_dependencies = globals['Modules'].get_all_external_dependencies(additional_modules=MINIMAL_MODULES)
        if external_dependencies:
            for key in sorted(external_dependencies):
                if not external_dependencies[key]:
                    continue
                click.secho("\nDetected external dependencies {}: {}".format(
                    key,
                    ', '.join(map(str, external_dependencies[key]))
                ), fg='green')

        tools = globals['tools']

        external_dependencies.setdefault('pip', [])
        external_dependencies.setdefault('deb', [])

        requirements_odoo = config.dirs['customs'] / 'odoo' / 'requirements.txt'
        if requirements_odoo.exists():
            for libpy in requirements_odoo.read_text().split("\n"):
                libpy = libpy.strip()

                if ';' in libpy or tools._extract_python_libname(libpy) not in (tools._extract_python_libname(x) for x in external_dependencies.get('pip', [])):
                    # gevent is special; it has sys_platform set - several lines;
                    external_dependencies['pip'].append(libpy)

        for libpy in lib_python_dependencies:
            if tools._extract_python_libname(libpy) not in (tools._extract_python_libname(x) for x in external_dependencies.get('pip', [])):
                external_dependencies['pip'].append(libpy)

        arr2 = []
        for libpy in external_dependencies['pip']:
            # PATCH python renamed dateutils to
            if 'dateutil' in libpy and PYTHON_VERSION >= (3, 8, 0):
                if not re.findall("python.dateutil.*", libpy):
                    libpy = libpy.replace('dateutil', 'python-dateutil')
            arr2.append(libpy)
        external_dependencies['pip'] = arr2

        for odoo_machine in odoo_machines:
            service = yml['services'][odoo_machine]
            service['build'].setdefault('args', [])
            py_deps = list(sorted(external_dependencies['pip']))
            service['build']['args']['ODOO_REQUIREMENTS'] = base64.encodebytes('\n'.join(py_deps).encode('utf-8')).decode('utf-8')
            service['build']['args']['ODOO_REQUIREMENTS_CLEARTEXT'] = (';'.join(py_deps).encode('utf-8')).decode('utf-8')
            service['build']['args']['ODOO_DEB_REQUIREMENTS'] = base64.encodebytes('\n'.join(sorted(external_dependencies['deb'])).encode('utf-8')).decode('utf-8')

        config.files['native_collected_requirements_from_modules'].parent.mkdir(exist_ok=True, parents=True)
        config.files['native_collected_requirements_from_modules'].write_text('\n'.join(external_dependencies['pip']))
