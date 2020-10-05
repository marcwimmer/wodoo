import yaml

def after_compose(config, settings, yml, globals):
    if settings['RESTART_CONTAINERS'] != "1":
        for service in yml['services']:
            if service == 'proxy':
                if settings['RUN_PROXY'] != "1":
                    yml['services'][service].pop('restart')
