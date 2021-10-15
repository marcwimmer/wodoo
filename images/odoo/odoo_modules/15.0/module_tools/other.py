from odoo import _
import base64
import datetime
from .dttools import str2date
import logging
import traceback
from odoo.exceptions import ValidationError
logger = logging.getLogger(__name__)

def decodeb64(content):
    content = content or ''
    return base64.b64decode(content)

def encodeb64(content):
    content = content or ''
    return base64.encodestring(content)

def floatify(adict, key):
    if not isinstance(adict[key], float):
        if isinstance(adict[key], int):
            adict[key] = float(adict[key])
        else:
            raise Exception(adict, key)

def slug(o):
    if not o:
        return o
    if isinstance(o, int):
        return o
    elif isinstance(o, (tuple, list)):
        return o[0]
    return o

def retry(f, maxtries=10, wait=2):
    tried = 0
    while True:
        try:
            f()
            return
        except Exception:
            tried += 1
            msg = traceback.format_exc()
            if tried > maxtries:
                logger.exception(msg)
                raise
            logger.debug('retrying...')
            import time
            time.sleep(wait)

def lookup(env, field_name, value, model):
    """
    returns the id of the record in the model
    if too many values found then error
    """

    found = env[model].search([(field_name, '=', value)])

    if len(found) == 0:
        raise ValidationError(_("No entry found in {} for value {}").format(model, value))
    elif len(found) > 1:
        raise ValidationError(_("Too many entries for {}:{}").format(model, value))
    return found

def Nzs(s):
    if s is None or s is False or not s:
        return ""
    return s

def get_proper_bool(val):
    res = False

    if val is None:
        return False

    if val.upper() == "TRUE": res = True
    elif val.upper() == "FALSE": res = False
    elif val.upper() == "JA": res = True
    elif val.upper() == "NEIN": res = False
    elif val == "1": res = True
    elif val == "0": res = False
    elif val == "": res = False
    else:
        raise Exception("invalid bool value: %s" % val)

    return res

def get_range_of_years(min, max):
    cyear = datetime.date.today().year
    years = []
    for i in range(0, min):
        year = cyear - min + i
        years.append((year, str(year)))

    years.append((cyear, str(cyear)))

    for i in range(1, max + 1):
        year = cyear + i
        years.append((year, str(year)))

    return years


def any_field_changed(old_dict, new_dict, field_list):
    """
    Checks, if any of the listed fields is changed in the
    dictionaries
    """
    if isinstance(field_list, (list, tuple)) is False:
        field_list = field_list,

    for f in field_list:
        if old_dict.get(f, False) != new_dict.get(f, False):
            return True
    return False
