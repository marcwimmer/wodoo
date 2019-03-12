#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x
if [[ -z "$1" ]]; then
    echo "Missing test-file"
    exit -1
fi

reset
source /eval_odoo_settings.sh
/apply-env-to-config.py

cd "$ADMIN_DIR/module_tools" || exit -1
module=$(python -c "import module_tools; print module_tools.get_module_of_file('$1')")
path="$ADDONS_CUSTOMS/$module/tests/$(basename "$1")"

sudo -E -H -u "$ODOO_USER" "$SERVER_DIR/$ODOO_EXECUTABLE" \
    -d "$DBNAME" \
    -c "$CONFIG_DIR/config_unittest" \
    --pidfile="$DEBUGGER_ODOO_PID" \
    --stop-after-init \
    --test-file="$path" \
    --test-report-directory=/tmp \
    --log-level=debug
