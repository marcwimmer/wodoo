import sys

def after_compose(config, yml, globals):
    if config.get("RUN_SSL"):
        if not config.get("SSLPROXY_SUBDOMAINS"):
            print("SSLPROXY_SUBDOMAINS missing")
            sys.exit(1)
