#!/usr/bin/python
import os
import sys

def add_upstream(location, upstream_instance, config_path):
# Place a file upstream.path in the root directory of machines
#
# /calendar http://davical:80/
# 1. parameter: the url you have to enter at the browser, here: http://<host>/calendar
# 2. parameter: upstream
# 3. parameter: output filename

    proxy_name = location.replace("/", "SLASH")
    url_balancer_manager = (location + "/__balancer_manager__").replace("//", "/")
    url_server_status = "/__server_status__"
    dollar = '$'
    with open(config_path, 'w') as f:
        f.write("""
#https://httpd.apache.org/docs/2.4/howto/reverse_proxy.html

<Proxy balancer://{proxy_name}>
    BalancerMember {upstream_instance} hcmethod=GET hcpasses=1 hcfails=1 hcinterval=2 hcuri=/
</Proxy>

<Location {url_server_status}>
    SetHandler server-status
    Require all granted
</Location>

<Location {url_balancer_manager}>
    SetHandler balancer-manager
    Require all granted
</Location>

ProxyPass {url_balancer_manager} !
ProxyPass {url_server_status} !
ProxyPass {location} balancer://{proxy_name}/
ProxyPassReverse {location} balancer://{proxy_name}/
""".format(**locals()).strip())
