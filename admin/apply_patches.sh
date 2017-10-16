#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x

statfile=$(mktemp -u)
echo 'good' > "$statfile"

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
if [[ -z "$ACTIVE_CUSTOMS" ]]; then
    echo "Customs Directory required!"
    exit -1
fi

if [[ -d "$SERVER_DIR" ]]; then
    echo ""
    echo ""
    echo "Applying patches: Customs $CUSTOMS Version $ODOO_VERSION in $SERVER_DIR"
    echo ""
    echo ""
    echo ""

    cd "$SERVER_DIR" || exit -1
	find "$ACTIVE_CUSTOMS" -name '*.patch' |grep "\/$ODOO_VERSION\/" | while read -r f
	do
        echo 
        echo 
        echo "Applying patch $f"
        echo "Working directory: $(pwd)"
		set +e
        git apply "$f"
		if [[ "$?" != "0" ]]; then
			echo 'error' > "$statfile"
			if [[ "$ALLOW_DIRTY_ODOO" != "1" ]]; then
				echo
				echo
				echo "Error at $f"
				echo
				echo
				exit -1
			fi
		fi
		set -e
    done

	echo
	echo
	echo
	errors=$(cat "$statfile")
	if [[ "$errors" == "good" ]]; then
		echo "Patches successfully applied!"
	else
		if [[ "$ALLOW_DIRTY_ODOO" == "1" ]]; then
			echo "Not all patches could be applied - but seems ok, since ALLOW_DIRTY_ODOO is set!"
		else
			echo "Error at applying patches."
		fi
	fi
	echo
	echo
    sleep 1
else
    echo "Server-Directory $SERVER_DIR not found - no patches applied."
    exit 0
fi
