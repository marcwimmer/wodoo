import yaml

def after_compose(config, settings, yml, globals):
    yml['services'].pop('proxy_abstract')
