# -*- coding: utf-8 -*-
import os
import re
import fnmatch
import pdb
import syslog
from lxml import etree
import sys
import tempfile
import shutil
import time
import traceback
from datetime import datetime
from odoo_config import odoo_root
from odoo_config import customs_dir
from odoo_config import current_customs
from odoo_config import plaintextfile
from odoo_config import current_version
from odoo_config import translate_path_relative_to_customs_root
from consts import MANIFEST_FILE
from consts import MANIFESTS
from consts import LN_FILE
cache_models = {}
cache_xml_ids = {}
modified_filename = ""

SEP_FILE = ":::"
SEP_LINENO = "::"

try:
    VERSION = current_version()
except Exception:
    VERSION = None

def ignore_file(full_path):
    if "/." in full_path:
        return True
    return False

def _determine_module(current_file):
    """
    identifies for the given file
    """
    current_path = os.path.dirname(current_file)
    counter = 0
    result = None

    def exists_manifest(current_path):
        for manifest in MANIFESTS:
            if os.path.exists("%s/%s" % (current_path, manifest)):
                return True
        return False

    while counter < 100 and len(current_path) > 1 and not exists_manifest(current_path):
        current_path = os.path.dirname(current_path)
        counter += 1
    if counter > 40:
        pass
    if current_path != "/":
        result = os.path.basename(current_path)
        try:
            float(result)
        except Exception:
            pass
        else:
            # is a version take parent path
            current_path = os.path.dirname(current_path)
            result = os.path.basename(current_path)
    return result

def try_to_get_filepath(filepath):
    if not os.path.isfile(filepath):
        candidates = []
        if filepath[0] != '/':
            filepath = '/' + filepath
        root = customs_dir()
        candidates.append((root + filepath).replace("//", "/"))
        for candidate in candidates:
            if os.path.isfile(candidate):
                filepath = candidate
                break
    if not os.path.isfile(filepath):
        raise Exception(u"not found: {}".format(filepath))
    while "//" in filepath:
        filepath = filepath.replace("//", "/")
    return filepath

def get_file_lineno(line):
    path, lineno = line.split(SEP_FILE)[1].split(SEP_LINENO)
    path = path.replace("//", "/")
    path = try_to_get_filepath(path)
    return path, int(lineno)

def get_view(inherit_id):
    with open(plaintextfile(), 'r') as f:
        token = "\t{}\t".format(inherit_id)
        content = f.read().split("\n")
        for line in content:
            if token in line:
                return get_file_lineno(line)
    return None, None

def manifest2dict(manifest_path):
    if not manifest_path:
        from pudb import set_trace
        set_trace()
        print traceback.format_stack()
        raise Exception('Missing manifest path')
    with open(manifest_path, 'r') as f:
        content = f.read()
    try:
        info = eval(content)
    except Exception:
        print "error at file: %s" % manifest_path
        raise
    return info

def get_manifest_file(module_dir):
    for x in MANIFESTS:
        if os.path.exists(os.path.join(module_dir, x)):
            return os.path.join(module_dir, x)
    return None

def is_module_of_version(path):
    if float(VERSION) >= 11.0:
        p = path
        while p and p != '/':
            if os.path.exists(os.path.join(os.path.abspath(p), MANIFEST_FILE)):
                break
            p = os.path.dirname(p)
        path = os.path.join(os.path.abspath(p), MANIFEST_FILE)
        if os.path.exists(path):
            manifest = manifest2dict(path)
            v = manifest.get('version', '0.0')
            if len(v.split('.')) < 4:
                # raise Exception("Manifest file {} contains invalid version: {}".format(path, v))
                return False
            return v.startswith(str(VERSION) + ".")
    else:
        p = path
        while p and p != '/':
            if os.path.exists(os.path.join(os.path.abspath(p), "__openerp__.py")):
                break
            if os.path.exists(os.path.join(os.path.abspath(p), LN_FILE)):
                break
            p = os.path.dirname(p)
        path = os.path.abspath(p)

        LNFILE = os.path.join(path, LN_FILE)
        if os.path.isfile(LNFILE):
            with open(LNFILE, 'r') as f:
                content = f.read()
            try:
                content = eval(content)
            except Exception:
                content = {}

            if isinstance(content, dict):
                _from = content.get('minimum_version', 0)
                _to = content.get('maximum_version', 9999)
            elif isinstance(content, (float, int, long)):
                _from = content
                _to = content
            result = VERSION >= _from and VERSION <= _to
            return result
        elif '/OCA/' in path:
            MANIFEST = os.path.join(path, "__openerp__.py")
            if os.path.exists(MANIFEST):
                return True
        return False


def walk_files(on_match, pattern):
    from module_tools import get_module_of_file

    def handle(path, dirs, files):
        if '/migration/' in path: # ignore migrations folder that contain OpenUpgrade
            return

        if is_module_of_version(path) or 'odoo/addons' in path:
            for filename in fnmatch.filter(files, pattern):
                filename = os.path.join(path, filename)
                if ignore_file(filename):
                    continue
                if os.path.basename(filename).startswith("."):
                    continue
                module = _determine_module(filename)
                with open(filename, "r") as f:
                    lines = f.read().split("\n")

                if modified_filename:
                    if modified_filename != filename:
                        continue

                on_match(filename, module, lines)

    if modified_filename:
        root = os.path.dirname(modified_filename)
        try:
            module, module_path = get_module_of_file(modified_filename, return_path=True)
        except Exception:
            # no module edited, ignore:
            return

        for path, dirs, files in os.walk(os.path.abspath(module_path), followlinks=False):
            if '.git' in dirs:
                dirs.remove('.git')
            handle(path, dirs, files)

    else:
        root = os.path.join(customs_dir()) # everything linked here...

        for path, dirs, files in os.walk(os.path.abspath(root), followlinks=False):
            if '.git' in dirs:
                dirs.remove('.git')
            handle(path, dirs, files)

def _get_methods():

    result = []

    def on_match(filename, module, lines):
        for linenumber, line in enumerate(lines):
            linenumber += 1
            methodname = re.search("def\ ([^\(]*)", line)
            if methodname:
                methodname = methodname.group(1)
                model = None
                if filename in cache_models:
                    if 'lines' in cache_models[filename]:
                        linenums = filter(lambda x: x < linenumber, cache_models[filename]['lines'].keys())
                        linenums.sort(lambda a, b: cmp(b, a))
                        model = None
                        if len(linenums) > 0:
                            model = cache_models[filename]['lines'][linenums[0]]

                    result.append({
                            'model': model,
                            'module': module,
                            'type': 'N/A',
                            'filename': os.path.basename(filename),
                            'filepath': filename,
                            'line': linenumber,
                            'method': methodname,
                    })
    walk_files(on_match, "*.py")

    return result

def _get_fields():

    result = []

    def on_match(filename, module, lines):
        for linenumber, line in enumerate(lines):
            linenumber += 1
            if "#" in line:
                line = line.split("#")[0]

            match = re.search(r"[\'\"]([^\'^\"]*)[\'\"].*fields\.", line)
            if match:
                fieldname = match.group(1)
            if not match:
                # V8
                match = re.search(r".*=.*fields\..*\(", line)
                if not match:
                    continue
                fieldname = match.group(0).split("=")[0].strip()
            if filename in cache_models and 'lines' in cache_models[filename]:
                linenums = filter(lambda x: x < linenumber, cache_models[filename]['lines'].keys())
                linenums.sort(lambda a, b: cmp(b, a))
                model = None
                if len(linenums) > 0:
                    model = cache_models[filename]['lines'][linenums[0]]

                result.append({
                    'model': model,
                    'module': _determine_module(filename),
                    'type': 'N/A',
                    'filename': os.path.basename(filename),
                    'filepath': filename,
                    'line': linenumber,
                    'field': fieldname
                })

    walk_files(on_match, "*.py")

    return result


def _get_views():

    result = []
    for id in cache_xml_ids['ids']:
        e = cache_xml_ids['ids'][id]
        if e['model'] == 'ir.ui.view':
            if not e['type'] and e['inherit_id']:
                parent = e
                BARRIER = 0
                while parent and parent['inherit_id'] and BARRIER < 10:
                    parent = cache_xml_ids['ids'].get(e['inherit_id'], None)
                    BARRIER += 1
                if parent:
                    e['type'] = parent['type']
            result.append(e)

    return result


def _get_xml_ids():
    result = []

    cache_xml_ids.setdefault('files', {})
    cache_xml_ids.setdefault('ids', {})

    def on_match(filename, module, lines):
        try:
            tree = etree.parse(filename)
        except Exception:
            return

        if filename not in cache_xml_ids["files"]:
            cache_xml_ids["files"][filename] = []

        def append_result(model, xmlid, line, res_model, name="", ttype="", inherit_id=""):

            if '.' not in xmlid:
                xmlid = "%s.%s" % (module, xmlid)

            # find res_models of view:
            if model and xmlid and '.' in xmlid:
                r = {
                    'module': module,
                    'model': model,
                    'id': xmlid,
                    'filename': os.path.basename(filename),
                    'filepath': filename,
                    'line': line,
                    'res_model': res_model,
                    "name": name,
                    "type": ttype,
                    "inherit_id": inherit_id,
                }

                cache_xml_ids["ids"][xmlid] = r
                cache_xml_ids["files"][filename].append(r)
                result.append(r)

        # get all records
        for r in tree.xpath("//record"):
            if "id" in r.attrib and "model" in r.attrib:
                id = r.attrib["id"]
                model = r.attrib["model"]

                res_model = r.xpath("field[@name='model' or @name='res_model']")
                if len(res_model) > 0:
                    res_model = res_model[0].text
                else:
                    res_model = ""

                if model == "ir.ui.menuitem":
                    name = r.xpath("field[@name='name']")[0].text
                    append_result(model, id, r.sourceline, '', name)
                elif model == "ir.ui.view":
                    name = ""
                    inherit_id = ""
                    if r.xpath("field[@name='name']"):
                        name = r.xpath("field[@name='name']")[0].text
                    if r.xpath("field[@name='inherit_id']"):
                        if r.xpath("field[@name='inherit_id']/@ref"):
                            inherit_id = r.xpath("field[@name='inherit_id']/@ref")[0]
                            if '.' not in inherit_id:
                                inherit_id = '{}.{}'.format(module, inherit_id)
                    ttype = ""
                    if not inherit_id:
                        if r.xpath("field[@name='arch']"):
                            arch = etree.tostring(r.xpath("field[@name='arch']")[0])
                            lines = [x.strip() for x in arch.split("\n")]
                            lines = [l for l in lines if l]
                            lines = lines[:5]

                            for line in lines:
                                for _t in ['form', 'tree', 'calendar', 'search', 'kanban']:
                                    token = "<{} ".format(_t)
                                    if token in line:
                                        ttype = _t
                    append_result(model, id, r.sourceline, '', name, ttype=ttype, inherit_id=inherit_id)
                else:
                    append_result(model, id, r.sourceline, res_model)

        for r in tree.xpath("//menuitem"):
            if "id" in r.attrib:
                id = r.attrib["id"]
                model = "ir.ui.menuitem"
                name = id
                try:
                    name = r.attrib["name"]
                except Exception:
                    # if there is no name, then name comes from
                    # associated action
                    try:
                        action = r.attrib['action']
                    except Exception:
                        action = ""

                    if action in cache_xml_ids:
                        name = cache_xml_ids[action].get("name")

                append_result(model, id, r.sourceline, '', name)

        for r in tree.xpath("//report"):
            if "id" in r.attrib:
                id = r.attrib["id"]
                model = "report"
                append_result(model, id, r.sourceline, '')

    walk_files(on_match, "*.xml")
    result.sort(lambda a, b: cmp(a["id"], b["id"]))

    return result

def _get_models():
    result = []

    def on_match(filename, unused, lines):
        with open(filename, "r") as f:
            lines = f.read().split("\n")

            def append_model(name, name_linenum, inherit, inherit_linenum):
                if name == "" and inherit == "":
                    return

                if name == "" and len(inherit) != "":
                    model = inherit
                    linenum = inherit_linenum
                    inherited = True
                else:
                    model = name
                    linenum = name_linenum
                    inherited = False

                global cache_models
                if filename not in cache_models:
                    cache_models[filename] = {'lines': {}, 'models': {}}
                if model not in cache_models[filename]['models']:
                    cache_models[filename]['models'][model] = []
                if "models" not in cache_models:
                    cache_models["models"] = {}
                if model not in cache_models["models"]:
                    cache_models["models"][model] = []
                cache_models[filename]['models'][model].append(linenum)
                cache_models[filename]['lines'][linenum] = model
                cache_models["models"][model].append({'file': filename, 'line': linenum, 'inherited': inherited})

            for linenum, line in enumerate(lines):
                linenum += 1

                osvregex = [
                    "class.*\(.*osv.*\)",
                    "class.*\(.*TransientModel.*\)",
                    "class.*\(.*Model.*\)",
                ]
                if any(re.match(x, line) for x in osvregex):
                    syslog.syslog("found line: {}\n".format(line))

                    _name = ""
                    _inherit = ""

                    for linenum1 in range(linenum, len(lines)):
                        line1 = lines[linenum1]
                        linenum1 += 1

                        if re.search("[\\\t\ ]_name.?=", line1):
                            _name = re.search("[\\\'\\\"]([^\\\'^\\\"]*)[\\\'\\\"]", line1)
                            if not _name:
                                # print "classname not found in: %s"%lines[i]
                                pass
                            else:
                                _name = _name.group(1)
                        elif re.search("[\\\t\ ]_inherit.?=", line1):
                            match = re.search("[\\\'\\\"]([^\\\'^\\\"]*)[\\\'\\\"]", line1)
                            if match:
                                _inherit = match.group(1)
                        elif any(re.match(x, line1) for x in osvregex):
                            # reached new class so append it
                            break

                    linenum_class = linenum # Zeilennummer der Klasse verwenden; es gibt Faelle z.B. stock.move, in denen _columns oberhalb von _name steht
                    append_model(_name, linenum_class, _inherit, linenum_class)
                    linenum = linenum1 - 1

    walk_files(on_match, "*.py")

    cache_models.setdefault("models", {})
    for m in cache_models["models"]:
        for l in cache_models["models"][m]:
            result.append({
                'model': m,
                'line': l['line'],
                'filepath': l['file'],
                'filename': os.path.basename(l['file']),
                'module': _determine_module(l['file']),
                'inherited': l['inherited']
            })
    return result

def _remove_entries(plain_text_file, rel_path):
    """
    Removes entries pointing to the relative path
    """
    with open(plain_text_file, 'r') as f:
        lines = f.readlines()
    match = "{}{}{}".format(SEP_FILE, rel_path, SEP_LINENO)
    temp = tempfile.mktemp(suffix='.tmp')
    os.system("cat '{plain_text_file}' | grep -v '{match}' > '{temp}'; cp '{temp}' '{plain_text_file}'".format(**locals()))

def update_cache(arg_modified_filename=None):
    """
    param: modified_filename - if given, then only this filename is parsed;
    """
    if arg_modified_filename:
        arg_modified_filename = os.path.realpath(arg_modified_filename)
    plainfile = plaintextfile()
    if not os.path.isfile(plainfile):
        arg_modified_filename = None

    customs = current_customs()
    if not customs:
        raise Exception("Customs required!")
    global cache_models
    global modified_filename
    modified_filename = arg_modified_filename

    try:
        rel_path = translate_path_relative_to_customs_root(modified_filename) if modified_filename else None
    except Exception:
        # suck errors - called from vim for all files
        return

    if arg_modified_filename and os.path.isfile(plainfile):
        _remove_entries(plainfile, rel_path)

    cache_models = {}
    xml_ids = _get_xml_ids()
    models = _get_models()
    methods = _get_methods()
    fields = _get_fields()
    views = _get_views()

    # get the relative module path and ignore everthing from that module;
    # the walk routine scanned the whole module
    from module_tools import get_module_of_file
    try:
        module, module_path = get_module_of_file(modified_filename, return_path=True)
        module_path = translate_path_relative_to_customs_root(module_path) + "/"
    except Exception:
        module_path = None

    if os.path.isfile(plainfile):
        f = open(plainfile, 'a')
    else:
        if os.path.isdir(os.path.dirname(plainfile)):
            f = open(plainfile, 'w')
        else:
            return

    try:
        TEMPLATE = "{type}\t[{module}]\t{name}\t" + SEP_FILE + "{filepath}" + SEP_LINENO + "{line}"
        for model in models:
            f.write(TEMPLATE.format(type="model", module=model['module'], name=model['model'], filepath=translate_path_relative_to_customs_root(model['filepath']), line=model['line']))
            f.write("\n")
        for xmlid in xml_ids:
            if '.' in xmlid['id']:
                name = xmlid['id']
            else:
                name = u"{}.{}".format(xmlid['module'], xmlid['id'])
            f.write(TEMPLATE.format(type="xmlid", module=xmlid['module'], name=name, filepath=translate_path_relative_to_customs_root(xmlid['filepath']), line=xmlid['line']))
            f.write("\n")
        for method in methods:
            name = u"{model}.{method}".format(**method)
            f.write(TEMPLATE.format(type="def", module=method['module'], name=name, filepath=translate_path_relative_to_customs_root(method['filepath']), line=method['line']))
            f.write("\n")
        for field in fields:
            name = u"{model}.{field}".format(**field)
            f.write(TEMPLATE.format(type="field", module=field['module'], name=name, filepath=translate_path_relative_to_customs_root(field['filepath']), line=field['line']))
            f.write("\n")
        for view in views:
            name = u"{res_model} ~{type} {id} [inherit_id={inherit_id}]".format(**view)
            f.write(TEMPLATE.format(type="view", module=view['module'], name=name, filepath=translate_path_relative_to_customs_root(view['filepath']), line=view['line']))
            f.write("\n")
    finally:
        f.close()

    return plainfile

def search_qweb(template_name, root_path=None):
    root_path = root_path or odoo_root()
    pattern = "*.xml"
    for path, dirs, files in os.walk(os.path.abspath(root_path), followlinks=True):
        if '.git' in dirs:
            dirs.remove('.git')
        for filename in fnmatch.filter(files, pattern):
            filename = os.path.join(path, filename)
            if "/static/" not in filename:
                continue
            if os.path.basename(filename).startswith("."):
                continue
            with open(filename, "r") as f:
                filecontent = f.read()
            for idx, line in enumerate(filecontent.split("\n")):
                for apo in ['"', "'"]:
                    if "t-name={0}{1}{0}".format(apo, template_name) in line and "t-extend" not in line:
                        return filename, idx + 1


def goto_inherited_view(filepath, line, current_buffer):
    line -= 1  # line ist einsbasiert
    sline = current_buffer[line]
    context = try_to_get_context(sline, current_buffer[:line + 1], filepath)

    filepath = None
    goto, filepath = None, None

    if isinstance(context, dict):
        if context["context"] == "arch" and "inherit_id" in context and context["inherit_id"]:
            inherit_id = context["inherit_id"]
            filepath, goto = get_view(inherit_id)

    if not filepath:
        # could be a qweb template
        for i in range(line, -1, -1):
            sline = current_buffer[i]
            if "t-extend=" in sline:
                sline = sline.split("t-extend=")[1]
                sline = sline.replace("\"", "'")
                template_name = sline.split("'")[1]
                return search_qweb(template_name)

    return filepath, goto


def try_to_get_context(line_content, lines_before, filename):
    result = None
    ext = ""
    if filename:
        _, ext = os.path.splitext(filename)

    # determine the last attribute if applicable:
    last_attribute = None

    if " " in line_content:
        t = line_content.split(" ")[-1]
        if "=" in t:
            t = t.split("=")[0]
        t = t.replace("\"", "")
        t = t.replace("\'", "")
        last_attribute = t

    if ext == "":
        pass
    elif ext in (".py", ".mako"):
        pass
    elif ext in (".xml"):
        if last_attribute == "parent":
            return "menuitem"
        elif last_attribute in ["src_model", "res_model"]:
            return "model"
        elif last_attribute in ["groups"]:
            return "group"

    field = False
    if "<field " in line_content and re.search("name=['\"]inherit_id['\"]", line_content) and last_attribute == "ref":
        return "view"
    elif "<field " in line_content and re.search("name=['\"]group_id['\"]", line_content) and last_attribute == "ref":
        return "group"
    elif "<field " in line_content and re.search("name=['\"]model['\"]", line_content):
        return "model"
    elif "<field " in line_content and re.search("name=['\"]model_id['\"]", line_content):
        return "model_id"

    elif "<field " in line_content and re.search("name=['\"]menu_id['\"]", line_content) and last_attribute == "ref":
        return "menuitem"
    elif re.search("<field.*name=['\"]$", line_content):
        field = True

    # check if we are in a view architecture:
    is_arch = False
    model = None
    inherit_id = None
    for i in range(len(lines_before)):
        line = lines_before[- i - 1]
        if re.search("<field.*name=['\"]arch['\"]", line):
            is_arch = True
        if re.search("<field.*name=['\"]inherit_id['\"]", line):
            try:
                inherit_id = re.search("\ ref=['\"]([^\"^']*)", line).group(1)
            except Exception:
                pass
        if re.search("<field.*name=['\"]model['\"]", line):
            try:
                model = re.search(".*>([^<]*)<", line).group(1)
            except Exception:
                pass

        if re.search("<record", line):
            if is_arch:
                return {'context': 'arch', 'model': model, 'field': field, 'inherit_id': inherit_id}
                break

    return result
