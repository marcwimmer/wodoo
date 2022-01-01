import yaml

def after_compose(config, settings, yml, globals):
    if 'proxy_abstract' in yml['services']:
        yml['services'].pop('proxy_abstract')
