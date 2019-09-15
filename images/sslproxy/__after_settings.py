def after_settings(config):
    if config['RUN_SSLPROXY'] == '1':
        config['RUN_PROXY_PUBLISHED'] = '0'
