#!/usr/bin/env bash
# Snapshot simple et vérifié du contenu /srv/labsite, envoyé à l'hôte 'backup'.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v docker >/dev/null || { echo 'Docker manquant' >&2; exit 1; }
compose() { docker compose --project-directory "$ROOT" "$@"; }

id="snapshot-$(date -u +%Y%m%dT%H%M%SZ)-$$"
dst="/srv/lab-backups/$id"
compose exec -T backup mkdir -p "$dst"
# Flux tar dans le réseau logique du lab. Les données restent sur le même hôte Docker physique.
compose exec -T web tar -C /srv/labsite -cf - . | compose exec -T backup tar -C "$dst" -xf -
source_hash="$(compose exec -T web sha256sum /srv/labsite/index.html | awk '{print $1}')"
backup_hash="$(compose exec -T backup sha256sum "$dst/index.html" | awk '{print $1}')"
[[ -n "$source_hash" && "$source_hash" == "$backup_hash" ]] || { echo 'Échec de la vérification SHA-256' >&2; exit 1; }
# Persist last successful snapshot ID inside the backup Docker volume.
printf '%s\n' "$id" | compose exec -T backup sh -c 'cat > /srv/lab-backups/LATEST'
printf '%s\n' "$source_hash" | compose exec -T backup sh -c "cat > '$dst/index.html.sha256'"
printf '[backup] %s sauvegardé sur le deuxième hôte ; SHA-256 confirmé : %s\n' "$id" "$source_hash"
printf '[backup] Restaurer : bash scripts/lab.sh restore %s\n' "$id"
