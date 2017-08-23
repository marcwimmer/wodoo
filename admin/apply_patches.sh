#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x

if [[ -z "$ODOO_VERSION" ]]; then
    echo "Version required!"
    exit -1
fi
if [[ -z "$CUSTOMS" ]]; then
    echo "Customs required!"
    exit -1
fi
if [[ -z "$SERVER_DIR" ]]; then
    echo "Server Directory required!"
    exit -1
fi
if [[ -z "$CUSTOMS_DIR" ]]; then
    echo "Customs Directory required!"
    exit -1
fi

if [[ -d "$SERVER_DIR" ]]; then
    echo "\n\n\nApplying patches: Customs $CUSTOMS Version $ODOO_VERSION in $SERVER_DIR"
    echo ""

    cd $SERVER_DIR
    for f in $(find $CUSTOMS_DIR -name '*.patch' |grep "\/$ODOO_VERSION\/"); do
        echo 
        echo 
        echo "Applying patch $f"
        echo "Working directory: $(pwd)"
        git apply "$f" || {
            echo "\n\n\n\nError at $f\n\n\n"
            exit -1
        }
    done

    echo "\n\n\nPatches successfully applied!"
    sleep 1
else
    echo "Server-Directory $SERVER_DIR not found - no patches applied."
    exit 0
fi
