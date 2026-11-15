#!/usr/bin/env bash
# Commandes de gestion du laboratoire. Déployer depuis le dépôt cloné.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
SECRETS="$ROOT/.secrets"

log() { printf '[linux-lab] %s\n' "$*"; }
fail() { printf '[erreur] %s\n' "$*" >&2; exit 1; }
require() { command -v "$1" >/dev/null || fail "Commande manquante : $1"; }
compose() { docker compose --project-directory "$ROOT" "$@"; }

init() {
  require ssh-keygen
  require python3
  mkdir -p "$SECRETS"
  chmod 0700 "$SECRETS"
  if [[ ! -f "$SECRETS/id_ed25519" ]]; then
    ssh-keygen -q -t ed25519 -N '' -C 'linux-infra-lab' -f "$SECRETS/id_ed25519"
    log 'Clé SSH de laboratoire créée dans .secrets/ (ignorée par Git).'
  else
    log 'Clé SSH déjà existante : conservée.'
  fi
  chmod 0600 "$SECRETS/id_ed25519"
  if [[ ! -f .env ]]; then
    password="$(python3 -c 'import secrets; print(secrets.token_hex(18))')"
    printf 'GRAFANA_ADMIN_PASSWORD=%s\n' "$password" > .env
    chmod 0600 .env
    log 'Mot de passe Grafana généré dans .env (ignoré par Git).'
  else
    log 'Fichier .env existant : conservé.'
  fi
}

check_ssh() {
  require ssh
  require ssh-keyscan
  local tmp
  tmp="$(mktemp "$SECRETS/.known_hosts.XXXXXX")"
  local done_scan=0
  for _ in $(seq 1 40); do
    if ssh-keyscan -T 1 -p 2221 127.0.0.1 > "$tmp" 2>/dev/null \
       && ssh-keyscan -T 1 -p 2222 127.0.0.1 >> "$tmp" 2>/dev/null; then
      done_scan=1; break
    fi
    sleep 1
  done
  [[ "$done_scan" -eq 1 ]] || { rm -f "$tmp"; fail 'Les serveurs SSH ne sont pas prêts.'; }
  chmod 0600 "$tmp"
  mv -f "$tmp" "$SECRETS/known_hosts"
  for port in 2221 2222; do
    ssh -i "$SECRETS/id_ed25519" -p "$port" \
      -o BatchMode=yes \
      -o StrictHostKeyChecking=yes \
      -o UserKnownHostsFile="$SECRETS/known_hosts" \
      -o ConnectTimeout=5 labadmin@127.0.0.1 true \
      || fail "Connexion SSH refusée sur le port $port"
  done
  log 'SSH par clé vérifié sur les deux hôtes Ubuntu.'
}

up() {
  require docker
  require ssh
  [[ -s "$SECRETS/id_ed25519.pub" ]] || fail 'Commencer par : bash scripts/lab.sh init'
  [[ -s .env ]] || fail 'Fichier .env absent : lancer init'
  compose up -d --build
  check_ssh
  log 'Services lancés. Étape suivante : bash scripts/lab.sh provision'
}

provision() {
  require ansible-playbook
  [[ -s "$SECRETS/known_hosts" ]] || fail 'Démarrer d’abord le lab (up)'
  ANSIBLE_HOST_KEY_CHECKING=True ansible-playbook \
    -i ansible/inventory.ini ansible/site.yml \
    --private-key "$SECRETS/id_ed25519" \
    --ssh-common-args "-o StrictHostKeyChecking=yes -o UserKnownHostsFile=$SECRETS/known_hosts -o BatchMode=yes"
  log 'Configuration Ansible terminée.'
}

test_lab() {
  require python3
  require curl
  require ssh
  check_ssh
  [[ "$(curl -fsS --max-time 10 http://127.0.0.1:8088/health)" == 'ok' ]] || fail 'Endpoint /health incorrect'
  curl -fsS --max-time 10 http://127.0.0.1:8088/ | grep -q 'déployé par Ansible' || fail 'Site Ansible introuvable'
  python3 scripts/check_metrics.py
  log 'Tous les tests de connectivité et de supervision ont réussi.'
}

backup() { bash scripts/backup.sh; }
restore() { bash scripts/restore.sh "${1:-}"; }

status() {
  require docker
  compose ps
  printf '\nInterfaces locales :\n'
  printf '  Site :         http://127.0.0.1:8088\n'
  printf '  Grafana :      http://127.0.0.1:3000\n'
  printf '  Prometheus :   http://127.0.0.1:9090\n'
  printf '  Alertmanager : http://127.0.0.1:9093\n'
}

incident() {
  require docker
  compose exec -T web supervisorctl stop nginx
  log 'Panne simulée : Nginx arrêté. Observer probe_success dans Prometheus et les alertes après 20 à 30 s.'
}
recover() {
  require docker
  compose exec -T web supervisorctl start nginx
  log 'Nginx redémarré. La sonde HTTP doit redevenir disponible.'
}

usage() {
  cat <<'HELP'
Usage : bash scripts/lab.sh <commande>
  init           Générer les clés SSH et le secret Grafana localement
  up             Construire et démarrer les conteneurs, vérifier SSH
  provision      Configurer les hôtes via Ansible (SSH)
  test           Vérifier SSH, HTTP, Prometheus, Grafana et alertes
  backup         Sauvegarder le site web sur le serveur de backup
  restore ID     Restaurer une sauvegarde identifiée par son ID
  incident       Arrêter volontairement Nginx pour tester une alerte
  recover        Redémarrer Nginx après l'incident
  status         Afficher l'état des conteneurs et les URL locales
  down           Arrêter le lab sans supprimer les volumes de données
HELP
}

case "${1:-}" in
  init) init ;;
  up) up ;;
  provision) provision ;;
  test) test_lab ;;
  backup) backup ;;
  restore) restore "${2:-}" ;;
  incident) incident ;;
  recover) recover ;;
  status) status ;;
  down) require docker; compose down; log 'Volumes conservés (backups et Grafana).' ;;
  *) usage; [[ -z "${1:-}" ]] && exit 0 || exit 2 ;;
esac
