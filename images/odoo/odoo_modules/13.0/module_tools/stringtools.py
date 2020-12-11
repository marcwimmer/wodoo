import re
from .dttools import str2date

# def replace(string_with_params, params):
    # new_params = []
    # for p in params: if not p:
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

def remove_double_space(txt):
    while "  " in txt:
        txt = txt.replace("  ", " ")
    return txt

def split_chars(to_split, chars, remove_double_space_before=True):
    if remove_double_space_before:
        to_split = remove_double_space(to_split)
    unique_string = "88assad!#!#!#!#!#df8fdsf$@14'12"
    for c in chars:
        to_split = to_split.replace(c, unique_string)
    return to_split.split(unique_string)
