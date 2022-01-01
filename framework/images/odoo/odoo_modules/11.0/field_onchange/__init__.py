def post_load():
    from .models import api
    api.monkeypatch()


from .models import *
from .tests import *
