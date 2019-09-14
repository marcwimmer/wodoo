import yaml

def after_compose(config, yml, globals):
    if config['RESTART_CONTAINERS'] != "1":
        for service in yml['services']:
            if service == 'proxy':
                if config['RUN_PROXY'] != "1":
                    yml['services'][service].pop('restart')
