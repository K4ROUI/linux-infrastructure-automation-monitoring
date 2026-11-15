# Exploitation et dépannage

## 1. Préparation

Utiliser **WSL2 Ubuntu** sur Windows (avec Docker Desktop WSL2 Integration activé) ou une distribution Linux avec Docker Engine, Compose, Ansible, OpenSSH et curl. Ne pas exécuter le lab directement dans l'invite CMD Windows. Les identifiants réels ne doivent jamais être copiés dans le dépôt.

```bash
bash scripts/lab.sh init
bash scripts/lab.sh up
bash scripts/lab.sh provision
bash scripts/lab.sh test
bash scripts/lab.sh status
```

L'initialisation conserve les clés et le mot de passe existants lors des appels suivants. Pour des conteneurs renouvelés, `up` reconstruit `.secrets/known_hosts` après récupération des nouvelles clés depuis localhost. Le dossier `.secrets/` et `.env` sont ignorés par Git.

## 2. Idempotence et diagnostic Ansible

```bash
bash scripts/lab.sh provision
bash scripts/lab.sh provision  # La deuxième exécution ne doit pas modifier les hôtes.
```

Pour explorer une panne SSH :

```bash
docker compose ps
docker compose logs --tail 100 web backup
ssh -vvv -i .secrets/id_ed25519 -p 2221 -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=.secrets/known_hosts labadmin@127.0.0.1
```

Si le port 2221 est occupé, stopper le service local qui l'utilise, ou modifier simultanément le mapping Compose et le port dans `ansible/inventory.ini` et `scripts/lab.sh`. Si `known_hosts` devient obsolète après reconstruction des conteneurs, relancer `bash scripts/lab.sh up` (et ne pas désactiver durablement la vérification SSH).

## 3. Diagnostic de Nginx

```bash
curl -v http://127.0.0.1:8088/health
docker compose exec web supervisorctl status nginx
docker compose exec web nginx -t
docker compose logs --tail 100 web
```

Le test `curl /health` garantit une réponse, mais pas la qualité du site entier. Tester aussi la page racine et le modèle déployé par Ansible.

## 4. Diagnostic Prometheus et Grafana

```bash
curl -fsS http://127.0.0.1:9090/-/ready
curl -fsS 'http://127.0.0.1:9090/api/v1/targets'
curl -fsS http://127.0.0.1:3000/api/health
python3 scripts/check_metrics.py
```

Dans Prometheus, explorer `up{job="node-linux"}` et `probe_success{job="http-health"}`. Un exporter à 1 et une sonde HTTP à 0 signifient que les métriques système sont disponibles, **mais que le service HTTP ne répond pas**.

## 5. Simuler puis corriger une panne

```bash
bash scripts/lab.sh incident
python3 scripts/check_alert.py --state firing
# Voir l'alerte WebServiceUnavailable dans http://127.0.0.1:9093
bash scripts/lab.sh recover
python3 scripts/check_alert.py --state resolved
bash scripts/lab.sh test
```

Ces étapes affectent seulement le conteneur `web`. Prometheus évalue les règles toutes les 5 s et attend 20 s d'échec avant de déclencher l'alerte. Les délais observés peuvent dépasser 20 s à cause de l'intervalle de collecte.

## 6. Sauvegarder et restaurer

```bash
bash scripts/lab.sh backup
# Un identifiant snapshot-AAAAMMJJTHHMMSSZ-PID est affiché.
bash scripts/lab.sh restore snapshot-AAAAMMJJTHHMMSSZ-PID
```

`backup.sh` utilise `tar` pour recopier `/srv/labsite` du web vers l'hôte backup et vérifie `index.html` par SHA-256. `restore.sh` vérifie l'archive puis restaure les fichiers **du site** dans `/srv/labsite`, sans remplacer `/etc/nginx`. Toutes les sauvegardes restent sur un volume Docker local, pas sur un serveur distant indépendant.

Pour lister les sauvegardes :

```bash
docker compose exec backup sh -c 'ls -l /srv/lab-backups'
docker compose exec backup sh -c 'cat /srv/lab-backups/LATEST'
```

### Option : programmer une sauvegarde quotidienne

Les sauvegardes ne sont **pas programmées automatiquement**. Depuis une installation Linux qui reste allumée, ajouter manuellement dans `crontab -e` (adapter le chemin réel) :

```cron
0 2 * * * cd /CHEMIN/ABSOLU/linux-infrastructure-automation-monitoring && /usr/bin/bash scripts/backup.sh >> /CHEMIN/ABSOLU/backup.log 2>&1
```

Le cron s'exécute dans le contexte du contrôleur, doit avoir accès à Docker, et **ne se déclenche pas si le PC est éteint**. Faire une rotation des journaux et des anciens snapshots si le lab doit fonctionner longtemps. Ne pas partager les mots de passe contenus dans `.env`.

## 7. Arrêter sans supprimer les sauvegardes

```bash
bash scripts/lab.sh down
```

`down` supprime les conteneurs et le réseau de ce projet, mais **conserve les volumes** : snapshots, base de données Grafana et métriques Prometheus. Si le conteneur `web` est recréé, relancer `up` puis `provision` ; les fichiers hors volumes propres au conteneur ne survivent pas à sa recréation.
