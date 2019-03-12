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
from .module_tools import get_module_of_file

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

if __name__ == '__main__':
    if len(sys.argv) <= 1:
        print("")
        print("")
        print("")
        print("Usage:")
        print("")
        print("tool.py static filename.js")
        print("")
        print("")
        print("")
        print("")
        sys.exit(0)

action = sys.argv[1]

def update_assets(module, assets_path, rel_path):
    # cheatsheet lxml
    with open(assets_path, 'r') as f:
        doc = etree.XML(f.read().strip())

    xpath = doc.xpath("//xpath")[0]

    rel_path = os.path.join(module, rel_path)

    if rel_path.endswith('.js'):
        if not xpath.xpath("script[@src='{}']".format(rel_path)):
            etree.SubElement(xpath, "script", {'type': 'text/javascript', 'src': rel_path})
    elif rel_path.endswith('.css') or rel_path.endswith('.less'):
        if not xpath.xpath("link[@href='{}']".format(rel_path)):
            etree.SubElement(xpath, "link", {'rel': 'stylesheet', 'href': rel_path})
    else:
        raise Exception("unhandled: {}".format(rel_path))

    with open(assets_path, 'w') as f:
        xml = etree.tostring(doc)
        f.write(xml)
