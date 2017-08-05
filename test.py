import configobj

ENCODING='utf-8'
from pudb import set_trace
set_trace()
conf = configobj.ConfigObj('customs.env', raise_errors=True,
    file_error=True,           # don't create file if it doesn't exist
    encoding=ENCODING,         # used to read/write file
    default_encoding=ENCODING) # str -> unicode internally (useful on Python2.x)

#conf.update(dict(ENABLEPRINTER='y', PRINTERLIST='PRNT3'))
#conf.write()
print conf.get('CUSTOMS')
