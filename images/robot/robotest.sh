#!/usr/bin/env bash
echo
echo "#######################################"
echo "# Recreate Robottest Config File      #"
echo "#######################################"
echo

FILE=./config_robottest.py

# Add default values to options
outputdir="output"
command="robot"
odooserver="localhost"
odoouser="admin"
odoopassword="1"
browser="headlesschrome"
alias="Headless Chrome"
driver="Chrome"
parallel="yes"
processes="1"

shareddata="no"
timecheck="no"
selenium_timeout="60"


_GETOPTS=":s:p:u:w:b:t:l:x:q:m:r:e:z:g:y:o:"
# Getops definitions:

# Options to regenerate the config_robottest.py file
# -s SERVER (default="http://localhost")
# -u ODOO_USER (default="admin")
# -w ODOO_PASSWORD (default="admin")
# -b BROWSER (default="headlesschrome")
# -l PARALLEL (default="yes")

# Options for launching the robot test
# -x Create share data (default="no")
# -m Running tests without/with multi option
#       1 (default) - launch of script with ${command}
#       >1          - launch of script with pabot and load users from users.dat file)
# -r Running again the tests that failed (default="no")
# -e Timecheck option in ${command} (default="no") - only for tests, not for shared data


# Use of the script
#
# Each time we launch the script, the config file config_robottest.py will be regenerated with the
# options send from the command line.
#
# First, to create the share data we have to launch the script with option "-x yes"
# ./robottest.sh -e no -x yes tests/complete/0001_new_contract.robot
#
# After the share data is created, we can omit the parameter -x to bypas the share data creation
# If share data is not created for the database, all tests will fail.
#
# For launching the script with multi process, add -m option and the number of processes
#
# If you test with odoo started with workers, add option "-p no" in the command line, if no server
# option is set, "localhost" will be REPLACED with "localhost".

while getopts "${_GETOPTS}" opt
do
    case "$opt" in
        s) odooserver=$OPTARG ;;
        o) outputdir=$OPTARG ;;
        u) odoouser=$OPTARG ;;
        w) odoopassword=$OPTARG ;;
        b) browser=$OPTARG ;;
        l) parallel=$OPTARG ;;
        x) shareddata=$OPTARG ;;
        m) processes=$OPTARG ;;
        e) timecheck=$OPTARG ;;
        z) selenium_timeout=$OPTARG ;;
    esac
done

shift $((OPTIND-1))

if [ "${browser}" == "headlessfirefox" ]; then
    alias="Headless Firefox"
    driver="Firefox"
fi
if [ "${browser}" == "chrome" ]; then
    alias="Chrome"
    driver="Chrome"
fi

# Update parallel config option if launch with multi processes
if [ ${processes} -ne 1 ]; then
    parallel="yes"
    timecheck="no"
fi

cat << EOF > $FILE

def get_variables():
    SERVER = "${odooserver}"
    return {
        # Time till the next command is executed
        "SELENIUM_DELAY": 0,
        # How long a "Wait Until ..." command should wait
        "SELENIUM_TIMEOUT": ${selenium_timeout},

        # Odoo
        "ODOO_URL": SERVER,
        "ODOO_URL_LOGIN": SERVER + "/web/login",
        "ODOO_USER": "${odoouser}",
        "ODOO_PASSWORD": "${odoopassword}",
        "BROWSER": "${browser}",
        "ALIAS": "${alias}",
        "DRIVER": "${driver}",
        "PARALLEL": "${parallel}",
    }
EOF

echo config created

if [ "${shareddata}" == "yes" ]; then
    echo
    echo "#######################################"
    echo "# Shared Data Creation                #"
    echo "#######################################"
    echo
    # initial file creation
    ${command} -v CONFIG:../config_robottest.py --variable TIMECHECK:no --outputdir "$outputdir" master
    RES1=$?
    echo "Setup Result :" $RES1
    # we keep a copy of the master log file
    cp output/log.html  output/master_log.html

    if [ $RES1 -ne 0 ]; then
        echo
        echo "#######################################"
        echo "# Shared Data Creation Second run     #"
        echo "#######################################"
        echo
        # Second run initial file creation
        ${command} -v CONFIG:../config_robottest.py --variable TIMECHECK:no --outputdir "$outputdir" master
        RES3=$?
        echo "Setup Result :" $RES3
        # we keep a copy of the first log file
        cp output/log.html  output/master_log.html
        if [ $RES3 -ne 0 ]; then
            echo
            echo "#######################################"
            echo "# Setup Fatal error !!!               #"
            echo "#######################################"
            echo
            exit $RES3
        fi
    fi
fi

echo
echo "#######################################"
echo "# Configuration used                  #"
echo "#######################################"
echo

cat "$FILE"

echo
echo "#######################################"
echo "# Running Test Suits first Time       #"
echo "#######################################"
echo

mkdir -p "$outputdir"

if [ "${processes}" == "1" ]; then
    ${command} --variablefile $FILE --variable TIMECHECK:${timecheck} --outputdir "$outputdir" "$@"
else
    pabot --pabotlib --resourcefile users.dat --processes ${processes} --variablefile $FILE --variable TIMECHECK:${timecheck} --outputdir "$outputdir" -N odootests "$@"
fi

RES2=$?
echo "Test Run Result (from robotest.sh):" $RES2

exit $RES2
