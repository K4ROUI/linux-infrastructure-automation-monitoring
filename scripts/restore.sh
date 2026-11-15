#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ID="${1:-}"
[[ "$ID" =~ ^snapshot-[0-9]{8}T[0-9]{6}Z-[0-9]+$ ]] || { echo 'Indiquer un ID de snapshot valide (ex. snapshot-20261115T120000Z-1234).' >&2; exit 2; }
command -v docker >/dev/null || { echo 'Docker manquant' >&2; exit 1; }
compose() { docker compose --project-directory "$ROOT" "$@"; }
path="/srv/lab-backups/$ID"
compose exec -T backup test -f "$path/index.html" || { echo "Snapshot introuvable : $ID" >&2; exit 1; }
expected="$(compose exec -T backup cat "$path/index.html.sha256")"
actual="$(compose exec -T backup sha256sum "$path/index.html" | awk '{print $1}')"
[[ "$expected" == "$actual" ]] || { echo 'Snapshot altéré : SHA-256 incorrect' >&2; exit 1; }
# On restaure seulement le répertoire /srv/labsite, pas la configuration Nginx.
compose exec -T backup tar -C "$path" --exclude='./index.html.sha256' -cf - . | compose exec -T web tar -C /srv/labsite -xf -
restored="$(compose exec -T web sha256sum /srv/labsite/index.html | awk '{print $1}')"
[[ "$expected" == "$restored" ]] || { echo 'Vérification post-restauration échouée' >&2; exit 1; }
printf '[restore] Snapshot %s restauré et vérifié : %s\n' "$ID" "$restored"
