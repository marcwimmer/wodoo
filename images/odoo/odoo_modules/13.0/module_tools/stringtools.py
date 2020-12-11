import re
from .dttools import str2date

# def replace(string_with_params, params):
    # new_params = []
    # for p in params:
        # if not p:
            # new_params.append("")
        # else:
            # new_params.append(p.decode("utf-8"))
    # result = string_with_params % tuple(new_params)
    # return result

#USE jinja or mako!
def replace_placholders(string, obj=False, parser=False, dict=False):
    pattern = '\$(.*?)\$' # (?<attrs>.*?)\$'
    matches = re.findall(pattern, string)
    for m in matches:
        try:
            if obj:
                attr = eval("%s.%s" % ('obj', m))
            elif dict:
                attr = dict[m]
            if attr:
                if parser:
                    date = False
                    try:
                        str2date(attr)
                        date = True
                    except Exception:
                        pass
                    if date:
                        attr = parser.formatLang(attr, date=date)
                string = string.replace("$%s$" % m, attr)
        except Exception:
            raise
    return string
