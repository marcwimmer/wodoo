#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x
$(
cd /opt/openerp/admin/module_tools
python -c"import module_tools; module_tools.remove_webassets()"
)
