import sys
import iptools.ipv4 as iptools
#BASE="10.28.0.0"
t = iptools.ip2long('127.0.0.1')
BASE = sys.argv[1]
offset = long(sys.argv[2])
l = iptools.ip2long(BASE)
l += offset
print iptools.long2ip(l)
