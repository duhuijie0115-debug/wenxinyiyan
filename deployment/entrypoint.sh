#!/bin/sh
set -eu
install -d -o app -g app -m 700 /home/app /tmp/runtime-app
if [ ! -s /home/app/.container-machine-id ]; then
    dbus-uuidgen > /home/app/.container-machine-id
    chown app:app /home/app/.container-machine-id
fi
cat /home/app/.container-machine-id > /etc/machine-id
exec /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf
