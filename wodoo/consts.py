from pathlib import Path
from .tools import _search_path

VERSIONS = [7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0]
YAML_VERSION = '3.7'
DEFAULT_IMAGES_REPO = "https://github.com/marcwimmer/wodoo-images"
IMAGES_REPO_BRANCH = "2024-09"

default_dirs = {
    'admin': 'admin',
    'odoo_home': '',
    'proxy_configs_dir': '${run}/proxy',
    'run': '${run}',
    'run/proxy': '${run}/proxy',
    'run/restore': '${run}/restore',
    'images/proxy': 'images/proxy',
    'telegrambot': 'config/telegrambat',
    'venv': "${run}/venv",
    'run_native_config_dir': '${run}/configs',
    'run_native_bin_dir': '${run}/bin',
    'run_native_requirements': '${run}/requirements', # requirement files
    'run_native_out_dir': '${run}/odoo_outdir',
    'odoo_tools': '$odoo_home',
    'odoo_data_dir': "~/.odoo/files",
    'user_conf_dir': "~/.odoo",
    'delegator': '~/.odoo/delegator',
    'images': '~/.odoo/images',
}

default_files = {
    'queuejob_channels_file': '${run}/queue-job-channels.txt',
    'odoo_docker_file': '${run}/Dockerfile.odoo',
    'after_reload_script': "/usr/local/bin/after-odoo-reload.sh",
    'after_up_script': "/usr/local/bin/after-odoo-up.sh",
    'odoo_config_file_additions': "~/.odoo/odoo.config",
    'odoo_config_file_additions.project': "~/.odoo/odoo.config.${project_name}",
    'project_settings': "~/.odoo/settings.${project_name}",
    'project_docker_compose.home': "~/.odoo/docker-compose.yml",
    'project_docker_compose.home.project': "~/.odoo/docker-compose.${project_name}.yml",
    'project_docker_compose.local': "${working_dir}/.odoo/docker-compose.${project_name}.yml",
    'docker_bin': _search_path('docker'),
    'docker_compose': '${run}/docker-compose.yml',
    'docker_compose_bin': _search_path('docker-compose'),
    'debugging_template_withports': 'config/template_withports.yml',
    'debugging_template_onlyloop': 'config/template_onlyloop.yml',
    'debugging_composer': '${run}/debugging.yml',
    'settings': '${run}/settings',
    'odoo_instances': '${run}/odoo_instances',
    'config/default_network': 'config/default_network',
    'config/cicd_network': 'config/cicd_network_for_project.yml',
    'run/odoo_debug.txt': '${run}/debug/odoo_debug.txt',
    'run/snapshot_mappings.txt': '${run}/snapshot_mappings.txt',
    'images/proxy/instance.conf': 'images/proxy/instance.conf',
    'commit': 'odoo.commit',
    'native_bin_install_requirements': "${run_native_bin_dir}/install-requirements",
    'native_bin_restore_dump': "${run_native_bin_dir}/restore-db",
    'native_collected_requirements_from_modules': "${run_native_bin_dir}/customs-requirements.txt",
    'start-dev': '~/.odoo/start-dev',
    'delegator_registry': '${delegator}/registry.json',
    'pgcli_history': '${run}/pgcli_history',
}

default_commands = {
    'dc': ['${docker_compose_bin}', "-p", "${project_name}", "-f",  "${docker_compose}"],
    'dc2': ['${docker_bin}', 'compose', "-p", "${project_name}", "-f",  "${docker_compose}"],
}

FILE_DIRHASHES = '.dirhashes'