# Architecture détaillée

## Un contrôleur et deux hôtes Linux administrables

Deux **conteneurs Ubuntu 24.04** sont construits à partir de `docker/ubuntu-host/Dockerfile`. Ils démarrent **sshd**, **Nginx** et **node_exporter** sous la surveillance locale de `supervisord`. Le contrôleur (Linux, ou Ubuntu sous WSL2) pilote leurs configurations avec **Ansible** via SSH.

| Réseau | Trajet | Usage |
| --- | --- | --- |
| Hôte → web `127.0.0.1:2221` | TCP/SSH → conteneur port 22 | Ansible et commandes distantes |
| Hôte → backup `127.0.0.1:2222` | TCP/SSH → conteneur port 22 | Ansible et diagnostic |
| Hôte → web `127.0.0.1:8088` | TCP → Nginx port 80 | Navigateur et health check |
| Prometheus → web/backup `:9100` | Réseau Docker `lab` | Scraping `node_exporter` |
| Prometheus → Blackbox `:9115` | Réseau Docker `lab` | Démarrage de la sonde HTTP |
| Blackbox → web `:80/health` | Réseau Docker `lab` | Test HTTP réel |
| Grafana → Prometheus `:9090` | Réseau Docker `lab` | Visualisation des séries |
| Prometheus → Alertmanager `:9093` | Réseau Docker `lab` | Livraison des alertes |

Les ports ouverts à l'hôte utilisent l'interface loopback **127.0.0.1**. Ils ne sont pas ouverts sur l'IP LAN du poste, sauf configuration externe non prévue ici. Toutes les dépendances vivent sur un même réseau `bridge` Docker local.

## Configuration SSH

- Une clé Ed25519 dédiée est générée dans `.secrets/id_ed25519` ; **jamais** commitée.
- Seule sa clé publique est montée en lecture seule dans les conteneurs et copiée vers l'utilisateur `labadmin`.
- SSH refuse l'accès root, les mots de passe et l'authentification interactive.
- `scripts/lab.sh up` récupère les clés d'hôte SSH depuis **localhost** par `ssh-keyscan`, puis réalise les connexions avec vérification des clés d'hôte enregistrées. Cette approche **TOFU (Trust On First Use)** n'est acceptable que pour le lab local ; en production, vérifier les empreintes via un canal de confiance.
- L'utilisateur `labadmin` dispose de `sudo` sans mot de passe **uniquement dans ce lab**. Ne jamais répliquer ce choix tel quel sur un hôte exposé.

## Gestion de configuration Ansible

Le playbook `ansible/site.yml` :

1. Configure `/etc/motd` et vérifie les outils de base sur les deux hôtes.
2. Déploie `/srv/labsite/index.html` via un modèle Jinja2 sur le web.
3. Déploie `/etc/nginx/sites-enabled/default` et redémarre Nginx **seulement si la configuration change**.
4. Prépare le répertoire de sauvegarde sur l'hôte `backup`.

**Idempotence :** une deuxième exécution ne doit pas modifier de fichiers déjà conformes. Le workflow CI vérifie l'absence de changements lors de la deuxième exécution.

## Signaux de supervision

La supervision teste trois couches différentes :

- **Disponibilité de l'exporter** (`up{job="node-linux"}`) : le réseau et l'endpoint metrics répondent.
- **Disponibilité applicative** (`probe_success{job="http-health"}`) : la sonde HTTP `/health` renvoie le code 200.
- **Configuration du déploiement** (Ansible + test HTTP dans `scripts/lab.sh test`) : la page web contient bien le marqueur issu du template.

La règle `WebServiceUnavailable` passe à `firing` après 20 secondes de sonde HTTP en échec ; `LinuxExporterUnavailable` signale un exporter inaccessible depuis 30 secondes. Les alertes arrivent dans Alertmanager pour observation locale, **sans destinataire externe**.

## Sauvegardes et limites

Une sauvegarde déclenchée sur le contrôleur transfère via un flux `tar` **du service Docker `web` vers `backup`** le contenu du répertoire `/srv/labsite`. Elle n'emprunte donc **pas** la connexion SSH Ansible, et ne sauvegarde **pas** une image système complète. Le transfert est limité aux conteneurs locaux de la machine Docker. Le répertoire `/srv/lab-backups` est un volume Docker persistant ; un stockage externe est nécessaire pour la tolérance à une panne de l'hôte.

Autres limites : aucun cluster, aucune haute disponibilité, pas de TLS, pas de DNS d'entreprise, ni d'identité/permission fine de production. Les métriques mémoire issues de `node_exporter` dans les conteneurs peuvent refléter les ressources du noyau hôte plutôt que des limites de conteneurs. Ce projet vise des **compétences d'administration**, pas une infrastructure conforme aux bonnes pratiques de production dans tous les aspects.
