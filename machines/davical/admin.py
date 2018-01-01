from pudb import set_trace
set_trace()
import requests
#r = requests.post("http://localhost:3333/reset_db", json={})

from pudb import set_trace
set_trace()

r = requests.post("http://localhost:3333/update_user", json={
    'user_no': 123,
    'username': 'user123',
    'email': 'max.mustermann@heidenei.de',
    'password': 'secret',
})
print r.text
from pudb import set_trace
set_trace()

r = requests.post("http://localhost:3333/new_user", json={
    'user_no': 123,
    'username': 'user123',
    'email': 'max.mustermann@heidenei.de',
    'password': 'secret',
})
print r.text
from pudb import set_trace
set_trace()

r = requests.post("http://localhost:3333/update_user", json={
    'user_no': 122,
    'password': 'secret1',
})
print r.text
from pudb import set_trace
set_trace()
