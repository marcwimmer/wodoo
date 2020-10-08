import re
import base64
import click
import yaml

def after_compose(config, settings, yml, globals):
    dirs = config.dirs
    odoodc = yaml.safe_load((dirs['odoo_home'] / 'images/odoo/docker-compose.yml').read_text())

    odoo_machines = set()

    # transfer settings from odoo_base into odoo, odoo_cronjobs
    for odoomachine in odoodc['services']:
        if odoomachine == 'odoo_base':
            continue
        if odoomachine not in yml['services']:
            continue
        odoo_machines.add(odoomachine)
        machine = yml['services'][odoomachine]
        for k in ['volumes']:
            machine[k] = []
            for x in yml['services']['odoo_base'][k]:
                machine[k].append(x)
        for k in ['environment']:
            machine.setdefault(k, {})
            if 'odoo_base' in yml['services']:
                for x, v in yml['services']['odoo_base'][k].items():
                    machine[k][x] = v
    if 'odoo_base' in yml['services']:
        yml['services'].pop('odoo_base')

    if settings['RESTART_CONTAINERS'] != "1":
        for service in yml['services']:
            # TODO CLEANUP -> more generic instructions ...
            if 'restart' in yml['services'][service] or \
                    (service == 'odoo_cronjobs' and not settings['RUN_ODOO_CRONJOBS']) or \
                    (service == 'proxy' and not settings['RUN_PROXY']):
                yml['services'][service].pop('restart')

        for service in yml['services']:
            for service_name, run in [
                ('odoo_cronjobs', settings['RUN_ODOO_CRONJOBS']),
                ('odoo_queuejobs', settings['RUN_ODOO_QUEUEJOBS']),
            ]:
                if service == service_name:
                    if not run:
                        yml['services'][service].pop('restart')

    if float(yml['services']['odoo']['environment']['ODOO_VERSION']) >= 13.0:
        # fetch dependencies from odoo lib requirements
        # requirements from odoo framework
        lib_python_dependencies = (dirs['odoo_home'] / 'requirements.txt').read_text().split("\n")

        # fetch the external python dependencies
        external_dependencies = globals['Modules'].get_all_external_dependencies()
        if external_dependencies:
            for key in external_dependencies:
                click.secho("Detected external dependencies {}: {}".format(
                    key,
                    ', '.join(map(str, external_dependencies[key]))
                ), fg='green')

        tools = globals['tools']

        external_dependencies.setdefault('pip', [])
        external_dependencies.setdefault('deb', [])

        # TODO hard coded default dependencies for framework modules like anonymization
        external_dependencies['pip'].append('names')

        requirements_odoo = config.dirs['customs'] / 'odoo' / 'requirements.txt'
        if requirements_odoo.exists():
            for libpy in requirements_odoo.read_text().split("\n"):
                libpy = libpy.strip()
                if tools._extract_python_libname(libpy) not in (tools._extract_python_libname(x) for x in external_dependencies.get('pip', [])):
                    external_dependencies['pip'].append(libpy)

        for libpy in lib_python_dependencies:
            if tools._extract_python_libname(libpy) not in (tools._extract_python_libname(x) for x in external_dependencies.get('pip', [])):
                external_dependencies['pip'].append(libpy)

        for odoo_machine in odoo_machines:
            service = yml['services'][odoo_machine]
            service['build'].setdefault('args', [])
            service['build']['args']['ODOO_REQUIREMENTS'] = base64.encodebytes('\n'.join(sorted(external_dependencies['pip'])).encode('utf-8')).decode('utf-8')
            service['build']['args']['ODOO_DEB_REQUIREMENTS'] = base64.encodebytes('\n'.join(sorted(external_dependencies['deb'])).encode('utf-8')).decode('utf-8')
