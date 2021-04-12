from .models import *
from .tests import *


def post_init(cr, registry):
    registry['ir.model.fields']._apply_default_anonymize_fields()