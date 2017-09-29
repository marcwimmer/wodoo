#!/usr/bin/python
# Console Tools
"""

Use

tool.py js          adds new javascript file


"""
import os
import sys
import lxml
from lxml import etree
from module_tools import get_module_of_file

ASSETS_PATH = "views/assets.xml"

ASSETS_BACKEND = """
<?xml version="1.0"?>
<odoo>
  <data>
    <template id="assets_backend" name="{module} assets" inherit_id="web.assets_backend">
      <xpath expr="." position="inside">
      </xpath>
    </template>
  </data>
</odoo>
"""

if len(sys.argv) <= 1:
    print ""
    print ""
    print ""
    print "Usage:"
    print ""
    print "tool.py js       -  new javascript"
    print "tool.py less     -  new less"
    print "tool.py webxml   -  new webxml"
    print ""
    print ""
    print ""
    print ""
    sys.exit(0)

action = sys.argv[1]

def update_assets(module, assets_path, rel_path):
    # cheatsheet lxml
    with open(assets_path, 'r') as f:
        doc = etree.XML(f.read().strip())

    xpath = doc.xpath("//xpath")[0]

    if rel_path.endswith('.js'):
        if not xpath.xpath("script[@src='{}']".format(rel_path)):
            etree.SubElement(xpath, "script", {'type': 'text/javascript', 'src': rel_path})
    elif rel_path.endswith('.css') or assets_path.endswith('.less'):
        if not xpath.xpath("link[@href='{}']".format(rel_path)):
            etree.SubElement(xpath, "link", {'rel': 'stylesheet', 'href': rel_path})
    else:
        raise Exception("unhandled: {}".format(rel_path))

    with open(assets_path, 'w') as f:
        xml = etree.tostring(doc)
        f.write(xml)


dir = os.getcwd()
module = get_module_of_file(dir)

if action in ['static']:

    try:
        filename = sys.argv[2]
    except:
        print "Please provide a filename e.g. file1.js"
        sys.exit(0)

    if not os.path.exists(os.path.join(dir, 'static')):
        os.mkdir(os.path.join(dir, 'static'))

    if not os.path.exists(os.path.join(dir, ASSETS_PATH)):
        with open(os.path.join(dir, ASSETS_PATH), 'w') as f:
            f.write(ASSETS_BACKEND.format(module=module).strip())
    relpath = 'static/src/{}'.format(action)
    try:
        os.makedirs(os.path.join(dir, relpath))
    except:
        pass
    update_assets(module, os.path.join(dir, ASSETS_PATH), os.path.join(relpath, filename))

    if not os.path.exists(os.path.join(relpath, filename)):
        with open(os.path.join(dir, relpath, filename), 'w') as f:
            f.write('')

    print
    print
    print
    print "Path to file:"
    print
    print
    print os.path.join(relpath, filename)
    print
    print

