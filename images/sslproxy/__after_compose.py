import sys

def after_compose(config, yml, globals):
    if config.run_ssl:
        if not config.sslproxy_subdomains:
            print("SSLPROXY_SUBDOMAINS missing")
            sys.exit(1)
