#!/usr/bin/env bash
set -Eeuo pipefail

[[ -s /run/lab/authorized_key.pub ]] || { echo 'Clé publique absente : lancer scripts/lab.sh init' >&2; exit 1; }
install -d -o labadmin -g labadmin -m 0700 /home/labadmin/.ssh
install -o labadmin -g labadmin -m 0600 /run/lab/authorized_key.pub /home/labadmin/.ssh/authorized_keys
# Generate unique SSH host keys for each fresh container, not image-wide shared keys.
ssh-keygen -A >/dev/null
exec /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf
