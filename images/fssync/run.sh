#!/bin/bash
usermod -u $OWNER_UID unison
echo "Starting unison server..."
chmod a+rwx /opt/target
chown $OWNER_UID -R /opt/target
su - unison -c "unison -socket 14122 -host 0.0.0.0"
