import subprocess
import click
from pathlib import Path
import os
import re
from lxml import etree
import tempfile
from .odoo_config import customs_dir
from .odoo_config import plaintextfile
from .odoo_config import translate_path_relative_to_customs_root
from contextlib import contextmanager

modified_filename = ""
cache_models = {}
cache_xml_ids = {}

SEP_FILE = ":::"
SEP_LINENO = ":"


def try_to_get_filepath(filepath):
    filepath = Path(filepath)
    if not filepath.is_file():
        candidates = []
        if str(filepath)[0] != "/":
            filepath = customs_dir() / filepath
        root = customs_dir()
        candidates.append((root / filepath))
        for candidate in candidates:
            if candidate.is_file():
                filepath = candidate
                break
    if not filepath.is_file():
        raise Exception(f"not found: {filepath}")
    filepath = filepath.resolve()
    return filepath


def get_file_lineno(line):
    path, lineno = line.split(SEP_FILE)[1].split(SEP_LINENO)
    path = path.replace("//", "/")
    path = try_to_get_filepath(path)
    return path, int(lineno)


def get_view(inherit_id):
    with plaintextfile().open("r") as f:
        lines = f.readlines()
        lines = filter(lambda line: inherit_id in line, lines)
        lines = filter(lambda line: re.search(rf"\D\ {inherit_id}\ \D", line), lines)
        lines = list(lines)
        if lines:
            return get_file_lineno(lines[0])
    return None, None


def get_qweb_template(name):
    with plaintextfile().open("r") as f:
        lines = f.readlines()
        lines = list(filter(lambda line: "~qweb" in line and name in line, lines))
        if lines:
            return get_file_lineno(lines[0])
    return None, None


def walk_files(on_match, pattern, name):
    from .module_tools import Module, Modules

    if modified_filename:
        try:
            mod = Module(modified_filename)
        except Module.IsNot:
            modules = Modules().modules.values()
        else:
            modules = [mod]
    else:
        modules = Modules().modules.values()

    files = []
    for mod in modules:
        for file in mod.path.glob("**/" + pattern):
            files.append((mod, file))

    with click.progressbar(files, label=f"Iterating files for {name}") as bar:
        for mod, file in bar:
            rel_file = file.relative_to(mod.path)
            if rel_file.parts[0] in [
                "migrations",
                "migration",
            ]:  # ignore migrations folder that contain OpenUpgrade
                continue
            if ".git" in file.parts:
                continue
            if file.name.startswith("."):
                continue

            lines = file.read_text(encoding="utf-8", errors="ignore").split("\n")
            on_match(file, mod, lines)


def _get_methods():

    result = []

    def on_match(filename, module, lines):
        for linenumber, line in enumerate(lines):
            linenumber += 1
            methodname = re.search(r"def\ ([^\(]*)", line)
            if methodname:
                methodname = methodname.group(1)
                model = None
                if filename in cache_models:
                    if "lines" in cache_models[filename]:
                        linenums = list(
                            reversed(
                                list(
                                    filter(
                                        lambda x: x < linenumber,
                                        cache_models[filename]["lines"].keys(),
                                    )
                                )
                            )
                        )
                        model = None
                        if len(linenums) > 0:
                            model = cache_models[filename]["lines"][linenums[0]]

                    result.append(
                        {
                            "model": model,
                            "module": module.name,
                            "type": "N/A",
                            "filename": os.path.basename(filename),
                            "filepath": filename,
                            "line": linenumber,
                            "method": methodname,
                        }
                    )

    walk_files(on_match, "*.py", "methods")

    return result


def _get_fields():

    result = []

    def on_match(filename, module, lines):
        for linenumber, line in enumerate(lines):
            linenumber += 1
            if "#" in line:
                line = line.split("#")[0]

            match = re.search(r".*=.*fields\..*\(", line)
            if match:
                fieldname = match.group(0).split("=")[0].strip()
            else:
                # V8
                match = re.search(r"[\'\"]([^\'^\"]*)[\'\"].*fields\.", line)
                if not match:
                    continue
                fieldname = match.group(1)
            if filename in cache_models and "lines" in cache_models[filename]:
                linenums = list(
                    reversed(
                        list(
                            filter(
                                lambda x: x < linenumber,
                                cache_models[filename]["lines"].keys(),
                            )
                        )
                    )
                )
                model = None
                if len(linenums) > 0:
                    model = cache_models[filename]["lines"][linenums[0]]

                result.append(
                    {
                        "model": model,
                        "module": module.name,
                        "type": "N/A",
                        "filename": os.path.basename(filename),
                        "filepath": filename,
                        "line": linenumber,
                        "field": fieldname,
                    }
                )

    walk_files(on_match, "*.py", "fields")

    return result


def _get_views():

    result = []
    for id in cache_xml_ids["ids"]:
        e = cache_xml_ids["ids"][id]
        if e["model"] == "ir.ui.view":
            if not e["type"] and e["inherit_id"]:
                parent = e
                BARRIER = 0
                while parent and parent["inherit_id"] and BARRIER < 10:
                    parent = cache_xml_ids["ids"].get(e["inherit_id"], None)
                    BARRIER += 1
                if parent:
                    e["type"] = parent["type"]
            result.append(e)

    return result


def _get_qweb_templates():
    result = []

    def on_match(filename, module, lines):
        if filename.relative_to(module.path).parts[0] != "static":
            return

        try:
            tree = etree.parse(filename)
        except Exception:
            return

        # get all records
        for r in tree.xpath("/templates/*"):
            if "t-name" in r.attrib:
                id = r.attrib["t-name"]
                extends = r.get("t-extend", "")

                if "." not in id:
                    id = "%s.%s" % (module.name, id)

                r = {
                    "type": "qweb",
                    "module": module.name,
                    "id": id,
                    "filename": os.path.basename(filename),
                    "filepath": filename,
                    "line": r.sourceline,
                    "name": id,
                    "inherit_id": extends,
                }

                result.append(r)

    walk_files(on_match, "*.xml", "qweb-templates")
    sorted(result, key=lambda x: x["name"])

    return result


def _get_xml_ids():
    result = []

    cache_xml_ids.setdefault("files", {})
    cache_xml_ids.setdefault("ids", {})

    def on_match(filename, module, lines):
        try:
            tree = etree.parse(str(filename))
        except TypeError:
            return
        except etree.XMLSyntaxError:
            return

        if filename not in cache_xml_ids["files"]:
            cache_xml_ids["files"][filename] = []

        def append_result(
            model, xmlid, line, res_model, name="", ttype="", inherit_id=""
        ):

            if "." not in xmlid:
                xmlid = "%s.%s" % (module.name, xmlid)

            # find res_models of view:
            if model and xmlid and "." in xmlid:
                r = {
                    "module": module.name,
                    "model": model,
                    "id": xmlid,
                    "filename": os.path.basename(filename),
                    "filepath": filename,
                    "line": line,
                    "res_model": res_model,
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
                    append_result(model, id, r.sourceline, "", name)
                elif model == "ir.ui.view":
                    name = ""
                    inherit_id = ""
                    if r.xpath("field[@name='name']"):
                        name = r.xpath("field[@name='name']")[0].text
                    if r.xpath("field[@name='inherit_id']"):
                        if r.xpath("field[@name='inherit_id']/@ref"):
                            inherit_id = r.xpath("field[@name='inherit_id']/@ref")[0]
                            if "." not in inherit_id:
                                inherit_id = f"{module}.{inherit_id}"
                    ttype = ""
                    if not inherit_id:
                        if r.xpath("field[@name='arch']"):
                            arch = etree.tostring(
                                r.xpath("field[@name='arch']")[0]
                            ).decode("utf-8")
                            lines = [x.strip() for x in arch.split("\n")]
                            lines = [l for l in lines if l]
                            lines = lines[:5]

                            for line in lines:
                                for _t in [
                                    "form",
                                    "tree",
                                    "calendar",
                                    "search",
                                    "kanban",
                                ]:
                                    token = f"<{_t} "
                                    if token in line:
                                        ttype = _t
                    append_result(
                        model,
                        id,
                        r.sourceline,
                        "",
                        name,
                        ttype=ttype,
                        inherit_id=inherit_id,
                    )
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
                        action = r.attrib["action"]
                    except Exception:
                        action = ""

                    if action in cache_xml_ids:
                        name = cache_xml_ids[action].get("name")

                append_result(model, id, r.sourceline, "", name)

        for r in tree.xpath("//report"):
            if "id" in r.attrib:
                id = r.attrib["id"]
                model = "report"
                append_result(model, id, r.sourceline, "")

        for r in tree.xpath("//template"):
            if "id" in r.attrib:
                id = r.attrib["id"]
                model = "ir.ui.view"
                inherit_id = ""
                if r.get("inherit_id"):
                    inherit_id = r.get("inherit_id")
                append_result(model, id, r.sourceline, "qweb", inherit_id=inherit_id)

    walk_files(on_match, "*.xml", "xml-ids")
    result.sort(key=lambda x: x["id"])

    for xmlid in result:
        if "." in xmlid["id"]:
            name = xmlid["id"]
        else:
            name = f"{xmlid['module']}.{xmlid['id']}"
        xmlid["fullname"] = name

    return result


def _get_models():
    result = []

    def on_match(filename, module, lines):
        with open(filename, "r") as f:
            lines = f.readlines()

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
                    cache_models[filename] = {"lines": {}, "models": {}}
                if model not in cache_models[filename]["models"]:
                    cache_models[filename]["models"][model] = []
                if "models" not in cache_models:
                    cache_models["models"] = {}
                if model not in cache_models["models"]:
                    cache_models["models"][model] = []
                cache_models[filename]["models"][model].append(linenum)
                cache_models[filename]["lines"][linenum] = model
                cache_models["models"][model].append(
                    {
                        "file": filename,
                        "line": linenum,
                        "inherited": inherited,
                        "module": module,
                    }
                )

            for linenum, line in enumerate(lines):
                linenum += 1

                osvregex = [
                    r"class.*\(.*osv.*\)",
                    r"class.*\(.*TransientModel.*\)",
                    r"class.*\(.*Model.*\)",
                ]
                if any(re.match(x, line) for x in osvregex):

                    _name = ""
                    _inherit = ""

                    for linenum1 in range(linenum, len(lines)):
                        line1 = lines[linenum1]
                        linenum1 += 1

                        if re.search(r"[\\\t\ ]_name.?=", line1):
                            _name = re.search("[\\'\\\"]([^\\'^\\\"]*)[\\'\\\"]", line1)
                            if not _name:
                                # print "classname not found in: %s"%lines[i]
                                pass
                            else:
                                _name = _name.group(1)
                        elif re.search(r"[\\\t\ ]_inherit.?=", line1):
                            match = re.search("[\\'\\\"]([^\\'^\\\"]*)[\\'\\\"]", line1)
                            if match:
                                _inherit = match.group(1)
                        elif any(re.match(x, line1) for x in osvregex):
                            # reached new class so append it
                            break

                    linenum_class = linenum  # Zeilennummer der Klasse verwenden; es gibt Faelle z.B. stock.move, in denen _columns oberhalb von _name steht
                    append_model(_name, linenum_class, _inherit, linenum_class)
                    linenum = linenum1 - 1

    walk_files(on_match, "*.py", "models")

    cache_models.setdefault("models", {})
    for m in cache_models["models"]:
        for l in cache_models["models"][m]:
            result.append(
                {
                    "model": m,
                    "line": l["line"],
                    "filepath": l["file"],
                    "filename": l["file"].name,
                    "module": l["module"].name,
                    "inherited": l["inherited"],
                }
            )
    return result


def _remove_entries(plain_text_file, rel_path):
    """
    Removes entries pointing to the relative path
    """
    match = f"{SEP_FILE}{rel_path}{SEP_LINENO}"
    try:
        temp = Path(tempfile.mktemp(suffix=".tmp"))

        os.system(
            (
                f"cat '{plain_text_file}' | "
                f"grep -v '{match}' > '{temp}'; "
                f"cp '{temp}' '{plain_text_file}'"
            )
        )
    finally:
        if temp.exists():
            temp.unlink()


def update_cache(arg_modified_filename=None):
    """
    param: modified_filename - if given, then only this filename is parsed;
    """
    from . import module_tools
    from .module_tools import Module, Modules

    if arg_modified_filename:
        arg_modified_filename = Path(arg_modified_filename).resolve().absolute()
    plainfile = plaintextfile()
    if not plainfile.is_file():
        arg_modified_filename = None

    if arg_modified_filename:
        try:
            Module(arg_modified_filename)
        except Module.IsNot:
            return

    global cache_models
    global modified_filename
    modified_filename = arg_modified_filename

    try:
        rel_path = (
            translate_path_relative_to_customs_root(modified_filename)
            if modified_filename
            else None
        )
    except Exception:
        # suck errors - called from vim for all files
        return

    if arg_modified_filename and plainfile.is_file():
        _remove_entries(plainfile, rel_path)

    cache_models = {}
    qwebtemplates = _get_qweb_templates()
    xml_ids = _get_xml_ids()
    models = _get_models()
    methods = _get_methods()
    fields = _get_fields()
    views = _get_views()

    if os.path.isfile(plainfile) and arg_modified_filename:
        f = open(plainfile, "a")
    else:
        if os.path.isdir(os.path.dirname(plainfile)):
            f = open(plainfile, "w")
        else:
            return

    def write_to_ast(content, ttype, get_name):
        TEMPLATE = (
            "{type}\t[{module}]\t{name}\t"
            + SEP_FILE
            + "{filepath}"
            + SEP_LINENO
            + "{line}"
        )
        with click.progressbar(content, label=f"Writing {ttype}...") as bar:
            for item in bar:
                f.write(
                    TEMPLATE.format(
                        type=ttype,
                        module=item["module"],
                        name=get_name(item),
                        filepath=translate_path_relative_to_customs_root(
                            item["filepath"]
                        ),
                        line=item["line"],
                    )
                )
                f.write("\n")

    try:
        TEMPLATE = (
            "{type}\t[{module}]\t{name}\t"
            + SEP_FILE
            + "{filepath}"
            + SEP_LINENO
            + "{line}"
        )
        write_to_ast(models, "model", lambda item: item["model"])
        write_to_ast(xml_ids, "xmlid", lambda item: item["fullname"])
        write_to_ast(methods, "method", lambda item: "{model}.{method}".format(**item))
        write_to_ast(fields, "field", lambda item: "{model}.{field}".format(**item))
        write_to_ast(
            views,
            "view",
            lambda item: "{res_model} ~{type} {id} [inherit_id={inherit_id}]".format(
                **item
            ),
        )
        write_to_ast(
            qwebtemplates,
            "qweb",
            lambda item: "~{type} {id} [inherit_id={inherit_id}]".format(**item),
        )
    finally:
        f.close()

    subprocess.run(f"sort -o '{plainfile}' -u '{plainfile}'", shell=True)
    subprocess.run(f"awk -i inplace '!seen[$0]++' '{plainfile}'", shell=True)

    return plainfile


def goto_inherited_view(filepath, line, current_buffer):
    line -= 1  # line ist einsbasiert
    sline = current_buffer[line]
    context = try_to_get_context(sline, current_buffer[: line + 1], filepath)

    filepath = None
    goto, filepath = None, None

    if isinstance(context, dict):
        if context["context"] in ["arch", "template"] and context.get(
            "inherit_id", False
        ):
            inherit_id = context["inherit_id"]
            filepath, goto = get_view(inherit_id)
        if context["context"] in ["qweb"] and context.get("inherit_id", False):
            inherit_id = context["inherit_id"]
            filepath, goto = get_qweb_template(inherit_id)

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
        t = t.replace('"', "")
        t = t.replace("'", "")
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
    if (
        "<field " in line_content
        and re.search("name=['\"]inherit_id['\"]", line_content)
        and last_attribute == "ref"
    ):
        return "view"
    elif (
        "<field " in line_content
        and re.search("name=['\"]group_id['\"]", line_content)
        and last_attribute == "ref"
    ):
        return "group"
    elif "<field " in line_content and re.search("name=['\"]model['\"]", line_content):
        return "model"
    elif "<field " in line_content and re.search(
        "name=['\"]model_id['\"]", line_content
    ):
        return "model_id"

    elif (
        "<field " in line_content
        and re.search("name=['\"]menu_id['\"]", line_content)
        and last_attribute == "ref"
    ):
        return "menuitem"
    elif re.search("<field.*name=['\"]$", line_content):
        field = True

    # check if we are in a view architecture:
    is_arch = False
    model = None
    inherit_id = None
    for i in range(len(lines_before)):
        line = lines_before[-i - 1]
        if re.search(r"<template\ ", line) and "<templates " not in line:
            inherit_id = re.search(r"\ inherit_id=['\"]([^\"^']*)", line)
            if inherit_id:
                inherit_id = inherit_id.group(1)
                return {
                    "context": "template",
                    "inherit_id": inherit_id,
                }
        if "<t " in line:
            inherit_id = re.search(r"\ t-extend=['\"]([^\"^']*)", line)
            if inherit_id:
                inherit_id = inherit_id.group(1)
                return {
                    "context": "qweb",
                    "inherit_id": inherit_id,
                }

        if re.search("<field.*name=['\"]arch['\"]", line):
            is_arch = True
        if re.search("<field.*name=['\"]inherit_id['\"]", line):
            try:
                inherit_id = re.search(r"\ ref=['\"]([^\"^']*)", line).group(1)
            except Exception:
                pass
        if re.search("<field.*name=['\"]model['\"]", line):
            try:
                model = re.search(".*>([^<]*)<", line).group(1)
            except Exception:
                pass

        if re.search("<record", line):
            if is_arch:
                return {
                    "context": "arch",
                    "model": model,
                    "field": field,
                    "inherit_id": inherit_id,
                }

    return result
