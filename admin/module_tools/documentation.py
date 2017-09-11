import ast
import pydot
import os
import tempfile
import time
import shutil
import graphviz
import jsonpickle
import json
import subprocess
import tabulate
from collections import OrderedDict
from consts import MANIFESTS
from odoo_config import customs_dir
from odoo_config import current_customs
from module_tools import get_module_of_file
from module_tools import get_relative_path_to_odoo_module
from module_tools import get_all_manifests
from module_tools import get_all_module_dependency_tree
from module_tools import is_module_listed_in_install_file_or_in_dependency_tree
from module_tools import manifest2dict

WIDTH_MOD_DEPENDENCY = "5cm"
WIDTH_MOD_CLASS_HIERARCHY = "5cm"

odoo_modules = {}
global_filepath = ""

def get_source_code(lineno, col_offset):
    with open(global_filepath, 'r') as f:
        content = f.read().split("\n")

        return content[lineno - 1][col_offset:]

class Interface(object):
    def __init__(self, heading_offset=0):
        """
        :param heading_offset: makes it possible to make module documentation on it
                               own
        """
        self.text = ""
        self.heading_offset = heading_offset
        self.heading_levels = "#*=-^\""

    def append(self, text):
        self.text += text + "\n"

    def remove_breaks(self, text):
        text = text.replace("\n", " ")
        return text

    def indent(self, text):
        result = []
        for line in text.split("\n"):
            line = "\t" + line
            result.append(line)
        return '\n'.join(result)

    def pagebreak(self):
        self.append(".. page::")

    def vertical_space(self):
        self.append(".. space::")

    def toc(self, depth=None, backlinks=False):
        self.append(".. contents:: Table of Contents")
        if depth:
            self.append(self.indent(':depth: {}'.format(depth)))
        if backlinks:
            assert backlinks in ['entry', 'top', 'none']
            self.append(self.indent(':backlinks: {}'.format(backlinks)))

    def tabulate(self, records):
        self.text += '\n'
        self.text += tabulate.tabulate(records, headers='keys', tablefmt='grid', numalign='right')
        self.text += '\n'

    def make_text(self):
        pass

    def get_heading_level(self, text):
        """
        returns minimum heading level 0 based of text
        """
        lowest_level = 100
        for line in text.split("\n"):
            for level, char in enumerate(self.heading_levels):
                if 4 * char in line:
                    lowest_level = min(lowest_level, level)
        return lowest_level

    def h1(self, text):
        self._heading(text, self.heading_offset + 0)

    def h2(self, text):
        self._heading(text, self.heading_offset + 1)

    def h3(self, text):
        self._heading(text, self.heading_offset + 2)

    def h4(self, text):
        self._heading(text, self.heading_offset + 3)

    def remove_empty_headings(self, text):
        lines = text.split("\n")
        result = []
        ignore_lines = set()
        for i, line in enumerate(lines):
            for c in self.heading_levels:
                if 4 * c in line:
                    if 4 * c in lines[i + 1]:
                        ignore_lines.add(i)
                        ignore_lines.add(i + 1)

            if i in ignore_lines:
                continue
            result.append(line)

        return '\n'.join(result)

    def increase_heading_level(self, text, inc):
        """
        inc = 1 then h1=>h2
        """

        levels = self.heading_levels
        lines = text.split("\n")
        result = []
        if inc >= 0:
            for line in lines:
                for level in reversed(range(len(levels))):
                    triple = 4 * levels[level]
                    if triple in line:
                        line = line.replace(levels[level], levels[level + inc])

                result.append(line)
        else:
            for line in lines:
                for level in range(len(levels)):
                    triple = 4 * levels[level]
                    if triple in line:
                        line = line.replace(levels[level], levels[level + inc])

                result.append(line)
        return '\n'.join(result)

    def _heading(self, text, level):
        text += "\n"
        text = self.remove_breaks(text)
        char = self.heading_levels[level - 1]
        self.append("\n\n")
        self.append(len(text) * char)
        self.append(text)
        self.append(len(text) * char)

    def ul(self, text):
        self.append("- {}".format(text))
        self.append("")

    def header(self, textblock):
        """
        rst2pdf params: ###Page###, ###Title###, ###Section###, ###SectNum###, ###Total###
        """
        self.append(".. header::")
        self.append(self.indent(textblock))

    def footer(self, textblock):
        """
        rst2pdf params: ###Page###, ###Title###, ###Section###, ###SectNum###, ###Total###
        """
        self.append(".. footer::")
        self.append(self.indent(textblock))

    def image_paragraph(self, path, width=None):
        """
        :param width: 3in, 80%, 7cm
        """
        self.append("\n.. image:: {}".format(path))
        if width:
            self.append(self.indent(":width: {}".format(width)))

class ModuleDataDocumentation(Interface):
    pass

class ModuleConfigurationDocumentation(Interface):
    pass

class ModuleDocumentation(Interface):
    def __init__(self, module, heading_offset=0):
        super(ModuleDocumentation, self).__init__(heading_offset=heading_offset)
        self.module = module

    def make_text(self):
        self.h1("Module: {}".format(self.module.name))

        self.append_graph_dependency()
        self.append_readme()
        self.append_description()
        self.append_tables()
        self.append_fields()
        self.append_field_helptexts()

    def append_tables(self):
        dot = pydot.Dot(graph_type='digraph')
        dot.set_node_defaults(shape='box')
        dot.set_edge_defaults(color='blue', arrowhead='vee', weight='0', labelangle='90')

        filename = tempfile.mktemp(suffix='.png')

        self.h2("Table Hierarchy")
        for classname, clazz in odoo_modules[self.module.name].clazzes.items():

            clazznode = pydot.Node(classname, fillcolor='grey', style='filled')

            for inherit in clazz.inherit:
                if inherit != classname:
                    inherit_node = pydot.Node(inherit)
                    dot.add_edge(pydot.Edge(inherit_node, clazznode))
                del inherit

            for inherit_field, inherit_from in clazz.inherits.items():
                inherit_node = pydot.Node(inherit_from)
                dot.add_edge(pydot.Edge(inherit_node, clazznode, label=inherit_field))
                del inherit_field
                del inherit_from

            dot.write_png(filename)
            self.image_paragraph(filename, WIDTH_MOD_CLASS_HIERARCHY)

    def append_fields(self):
        self.h2("Fields")
        for classname, clazz in odoo_modules[self.module.name].clazzes.items():
            records = []
            order = ['Model', 'Field', 'Type', 'Comodel', 'Compute', 'Relate', 'Selection']
            for field in clazz.fields:
                records.append(OrderedDict(sorted({
                    'Model': clazz.name,
                    'Field': field.name,
                    'Type': field.ttype,
                    'Comodel': field.params.get('comodel_name', "n/a"),
                    'Relate': field.params.get('relate', "n/a"),
                    'Selection': str(field.params.get('selection', "n/a")),
                }.items(), key=lambda x: order.index(x[0]))))
            self.tabulate(records)

    def append_field_helptexts(self):
        self.h2("Field Helptexts")
        for classname, clazz in odoo_modules[self.module.name].clazzes.items():
            records = []
            order = ['Model', 'Field', 'Help']
            for field in clazz.fields:
                if not field.params.get('help', False):
                    continue
                records.append(OrderedDict(sorted({
                    'Model': clazz.name,
                    'Field': field.name,
                    'Help': self.remove_breaks(field.params.get('help')),
                }.items(), key=lambda x: order.index(x[0]))))
            self.tabulate(records)

    def append_graph_dependency(self):
        filename = self.module.get_graphviz()
        self.h2("Module Dependency Diagram")
        self.image_paragraph(filename, WIDTH_MOD_DEPENDENCY)

    def append_description(self):
        if self.module.manifest.get('description', False):
            self.h2("Description")
            self.append(self.module.manifest['description'])

    def append_readme(self):
        readme_path = os.path.join(os.path.dirname(self.module.manifest_path), 'README.rst')
        if os.path.isfile(readme_path):
            with open(readme_path, 'r') as f:
                content = f.read()

                # remove modulename  with heading
                lines, lines2 = content.split("\n"), []
                for line in lines:
                    if self.module.name == line:
                        continue
                    lines2.append(line)
                content = '\n'.join(lines2)
                content = self.remove_empty_headings(content) # could be empty, because module name was removed

                readme_level = self.get_heading_level(content)

                content = self.increase_heading_level(content, self.heading_offset + 1 - readme_level) # -2 no
                self.h2("Readme")
                self.append(content)

class CustomsDocumentation(Interface):

    def __init__(self):
        super(CustomsDocumentation, self).__init__()
        self.customs = current_customs()

    def make_text(self):
        self.h1("Documentation odoo {}".format(self.customs))
        self.toc(depth=2)
        self.pagebreak()
        self.header("Odoo Documentation")
        self.footer("Page ###Page### of ###Total###")

        for module in sorted(odoo_modules.values(), key=lambda mod: mod.name):
            doc = ModuleDocumentation(module, heading_offset=self.heading_offset + 1)
            doc.make_text()
            self.append(doc.text)


def set_parents(tree):
    "nice trick to set parent everywhere first"
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node
    return tree

class OdooModule(object):
    def __init__(self, manifest_path):
        self.name = get_module_of_file(manifest_path)
        self.manifest_path = manifest_path
        self.manifest = manifest2dict(manifest_path)
        self.version = self.manifest.get('version', "")
        self.depends = self.manifest.get('depends', [])
        self.clazzes = {}
        if self.name in odoo_modules:
            raise Exception("module {} already exists")
        odoo_modules[self.name] = self

    def get_graphviz(self, filename=None):
        if not filename:
            filename = tempfile.mktemp(suffix='.png')
        dot = pydot.Dot(graph_type='digraph')
        dot.set_node_defaults(shape='box')
        dot.set_edge_defaults(color='blue', arrowhead='vee', weight='0', labelangle='90')

        def handle_ancestors(pre, ancs):
            for anc in ancs:
                if isinstance(anc, (str, unicode)):
                    node = pydot.Node(anc)
                else:
                    attrs = {}
                    if anc.name == self.name:
                        attrs['fillcolor'] = 'darkorchid1'
                        attrs['style'] = 'filled'
                    node = pydot.Node(anc.name, **attrs)

                dot.add_node(node)
                if pre:
                    dot.add_edge(pydot.Edge(pre, node))
                if not isinstance(anc, (str, unicode)):
                    handle_ancestors(node, [odoo_modules.get(x, x) for x in anc.depends])

        handle_ancestors(None, [self])
        dot.write_png(filename)
        return filename

class OdooModel(object):
    def __init__(self, name, inherit, inherits):
        super(OdooModel, self).__init__()

        if not name and inherit:
            name = inherit
        self.name = name
        self.inherit = []
        self.inherits = {}
        self.locations = []
        self.defs = []
        self.fields = []

        if inherit:
            if isinstance(inherit, (str, unicode)):
                inherit = [inherit]
            self.inherit = inherit

        if inherits:
            if not isinstance(inherits, dict):
                raise Exception("inherits must be a dict")
            self.inherits = inherits

    class Location(object):
        def __init__(self, module, rel_filepath, lineno):
            self.module = module
            self.rel_filepath = rel_filepath
            self.lineno = lineno

    class OdooCodePart(object):
        def __init__(self, location, parent, name):
            self.name = name
            self.location = location
            self.parent = parent

    class OdooDef(OdooCodePart):
        def __init__(self, parent, location, name):
            super(OdooModel.OdooDef, self).__init__(location, parent, name)

    class OdooField(OdooCodePart):
        def __init__(self, parent, location, name, ttype, params):
            super(OdooModel.OdooField, self).__init__(location, parent, name)
            self.ttype = ttype
            self.params = params
            self.help = params.get('help', "")

class OdooParser(ast.NodeVisitor):
    def __init__(self, modules):
        """
        :param rel_filepath: relative filepath to module
        """
        super(OdooParser, self).__init__()
        self.module = None
        self.rel_filepath = None
        self.modules = modules

    def set_module(self, module):
        self.module = module
        self.modules.setdefault(module.name, {})

    def get_parent_until(self, node, clazz):
        p = node
        while not isinstance(p, clazz):
            p = p.parent
        return p

    def get_field_name(self, node):
        """

        class A:
            _inherit = "..."

        finds _inherit

        _inherit = is an assign
        """
        try:
            a = self.get_parent_until(node, ast.Assign)
        except:
            return None
        return a.targets[0].id

    def interprete_field_node(self, node):
        ttype = node.func.attr
        params = {}

        def get_param_value(value, name=None):
            if name == 'store':
                if isinstance(value, ast.Dict):
                    return True
                elif isinstance(value, ast.Name):
                    return value.id
                else:
                    raise Exception("unhandled")

            elif isinstance(value, (ast.List, ast.Tuple)):
                value2 = []
                for v in value.elts:
                    v = get_param_value(v, name)
                    value2.append(v)
                value = value2
            elif isinstance(value, ast.Dict):
                d = {}
                for i, key in enumerate(value.keys):
                    v = value.values[i]
                    v = get_param_value(v)
                    d[key] = v
                value = d
            elif isinstance(value, ast.Str):
                value = value.s
            elif isinstance(value, ast.Num):
                value = value.n
            elif isinstance(value, ast.Name):
                value = value.id
            elif isinstance(value, ast.Lambda):
                value = get_source_code(value.lineno, value.col_offset)
            elif isinstance(value, ast.ListComp):
                value = get_source_code(value.lineno, value.col_offset)
            else:
                from pudb import set_trace
                set_trace()
                raise Exception("Unhandled: {}".format(value.__class__))
            return value

        for idx, arg in enumerate(node.args):
            if ttype.lower() == 'many2many':
                if idx == 0:
                    params['comodel_name'] = arg.s
                elif idx == 1:
                    params['relation'] = arg.s
                elif idx == 2:
                    params['column1'] = arg.s
                elif idx == 3:
                    params['column2'] = arg.s
                elif idx == 4:
                    params['string'] = arg.s
                else:
                    raise Exception("unhandled")

            elif ttype.lower() == 'one2many':
                if idx == 0:
                    params['comodel_name'] = arg.s
                elif idx == 1:
                    params['inverse_name'] = arg.s
                elif idx == 2:
                    params['string'] = arg.s
                else:
                    raise Exception("unhandled")

            elif ttype.lower() == 'many2one':
                if idx == 0:
                    params['comodel_name'] = arg.s
                elif idx == 1:
                    params['string'] = arg.s
                else:
                    raise Exception("unhandled")

            elif ttype.lower() == 'function':
                if idx == 0:
                    params['compute'] = get_param_value(arg)
                else:
                    raise Exception("unhandled")

            elif ttype.lower() == 'selection':
                if idx == 0:
                    params['selection'] = get_param_value(arg)
                elif idx == 1:
                    params['string'] = get_param_value(arg)
                else:
                    raise Exception("unhandled")

            elif ttype.lower() == 'related':
                params.setdefault('relate', "")
                params['relate'] += '.' + get_param_value(arg)
                if params['relate'].startswith('.'):
                    params['relate'] = params['relate'][1:]

            else:
                if idx == 0:
                    params['string'] = get_param_value(arg)
                else:
                    from pudb import set_trace
                    set_trace()
                    raise Exception("unhandled")

        for keyword in node.keywords:
            if keyword.arg in params:
                raise Exception("Already in dict: {}".format(keyword.arg))
            params[keyword.arg] = get_param_value(keyword.value, keyword.arg)

        if hasattr(node.func, 'id'):
            ttype = node.func.id
        elif hasattr(node.func, 'attr'):
            ttype = node.func.attr
        else:
            raise Exception("Unhandled: {}".format(node.func))

        return ttype, params

    def visit_ClassDef(self, node):
        """
        Set context to odoo class
        """
        self.current_classdef = node
        self.current_class_name = None
        attrs = {}
        fields = {}
        defs = {}
        for statement in node.body:
            if isinstance(statement, ast.Assign):
                if len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):

                    if isinstance(statement.value, ast.Str):
                        fieldname = statement.targets[0].id
                        attrs[fieldname] = statement.value.s

                    elif isinstance(statement.value, ast.List) and statement.targets[0].id == "_inherit":
                        attrs['_inherit'] = [x.s for x in statement.value.elts]

                    elif isinstance(statement.value, ast.Dict) and statement.targets[0].id == "_inherits":
                        attrs['_inherits'] = {}
                        for i in range(len(statement.value.values)):
                            key = statement.value.keys[i].s
                            value = statement.value.values[i]
                            attrs['_inherits'][key] = value.s

                    elif isinstance(statement.value, ast.Dict) and statement.targets[0].id == "_columns":
                        for i in range(len(statement.value.values)):
                            fieldname = statement.value.keys[i].s
                            value = statement.value.values[i]
                            ttype, params = self.interprete_field_node(value)
                            fields[fieldname] = {
                                'ttype': ttype,
                                'params': params,
                                'node': value,
                            }

                    elif isinstance(statement.value, ast.Call):

                        fieldname = statement.targets[0].id
                        ttype, params = self.interprete_field_node(statement.value)

                        fields[fieldname] = {
                            'ttype': ttype,
                            'params': params,
                            'node': statement.value,
                        }

            if isinstance(statement, ast.FunctionDef):
                defs[statement.name] = statement

        self.current_class_name = attrs.get("_name", attrs.get("_inherit", None))
        if not self.current_class_name:
            # TODO _name from class name?
            self.current_classdef = None

        if self.current_class_name:
            if self.current_class_name not in self.module.clazzes:
                clazz = self.module.clazzes[self.current_class_name] = OdooModel(
                    attrs.get('_name', None),
                    attrs.get('_inherit', None),
                    attrs.get('_inherits', None),
                )
            else:
                clazz = self.module.clazzes[self.current_class_name]

            clazz.locations.append(OdooModel.Location(self.module, self.rel_filepath, node))

            for defname, defnode in defs.items():
                location = OdooModel.Location(self.module, self.rel_filepath, node)
                clazz.defs.append(OdooModel.OdooDef(self, location, defname))

            for fieldname, field in fields.items():
                location = OdooModel.Location(self.module, self.rel_filepath, field['node'])
                clazz.fields.append(OdooModel.OdooField(self, location, fieldname, field['ttype'], field['params']))

    def visit_Str(self, node):
        pass

    def generic_visit(self, node):
        ast.NodeVisitor.generic_visit(self, node)

    def visit(self, tree):
        if not self.module:
            raise Exception("Module missing!")
        if not self.rel_filepath:
            raise Exception("Rel-Filepath missing!")
        self.current_classdef = None
        self.current_class_name = None
        return super(OdooParser, self).visit(tree)

def parse_all_modules():
    # parse odoo classes and modules
    all_manifests = list(get_all_manifests())
    all_deps = get_all_module_dependency_tree()
    filtered_manifests = [
        x
        for x
        in all_manifests
        if is_module_listed_in_install_file_or_in_dependency_tree(get_module_of_file(x), all_manifests=all_manifests, all_module_dependency_tree=all_deps)
    ]

    parser = OdooParser(odoo_modules)
    global global_filepath
    for manifest in filtered_manifests:
        parser.set_module(OdooModule(manifest))
        if not parser.module:
            continue
        for root, dirs, files in os.walk(os.path.dirname(manifest)):
            for file in files:
                filepath = os.path.join(root, file)
                global_filepath = filepath
                if filepath.endswith(".py") and file not in MANIFESTS:
                    with open(filepath, 'r') as f:
                        tree = ast.parse(f.read())
                        set_parents(tree) # patch
                        parser.rel_filepath = get_relative_path_to_odoo_module(filepath)
                        parser.visit(tree)


if __name__ == '__main__':
    parse_all_modules()
    filename = tempfile.mktemp(suffix='.clazzes')
    # with open('/tmp/clazzes.txt', 'w') as f:
    #    f.write(json.dumps(json.loads(jsonpickle.encode(odoo_classes, unpicklable=True)), sort_keys=True, indent=4, separators=(',', ': ')))

    doc = CustomsDocumentation()
    doc.make_text()

    filename = tempfile.mktemp(suffix='.txt')
    with open(filename, 'w') as f:
        f.write(doc.text)
    os.system('terminator -x vim {}'.format(filename))

    pdf_path = "{}.pdf".format(filename)
    os.system("rst2pdf \"{}\" \"{}\"".format(
        filename,
        pdf_path
    ))

    subprocess.check_call(['/usr/bin/evince', pdf_path])
    print filename
