# Plan de validation, preuve et état actuel

## Résultats réels sur Ubuntu 24.04 (GitHub Actions)

**Exécution réussie le 15 novembre 2026 :** [voir le journal complet des tests](https://github.com/K4ROUI/linux-infrastructure-automation-monitoring/actions/runs/43718378358), sur le commit `1ad175f4241106bff371a5846d4c42ffad59cae5`.

La CI confirme : tests statiques et syntaxe, connexion SSH par clés sur deux conteneurs Ubuntu, configuration Ansible idempotente (`changed=0` à la seconde exécution), HTTP et exporters Prometheus disponibles, API Grafana, copie/restauration avec contrôle SHA-256, puis arrêt de Nginx, alerte `WebServiceUnavailable` active et alerte résolue après redémarrage.

**Limites de preuve :** les tests n'authentifient pas de captures Grafana personnelles, ne mesurent pas de performances et ne démontrent aucun déploiement sur plusieurs VM ou serveurs physiques. La présence des fichiers de provisioning Grafana est contrôlée statiquement ; l'exécution de supervision contrôle son API de santé.

## Ce que les fichiers doivent permettre de tester

| Vérification | Méthode | Résultat attendu | Résultat réel |
| --- | --- | --- | --- |
| Scripts et configurations corrects | `python3 -m unittest discover -s tests -v` | Tests statiques réussis | [**Réussi en CI**](https://github.com/K4ROUI/linux-infrastructure-automation-monitoring/actions/runs/43718378358) |
| Syntaxe Bash | `for f in scripts/*.sh docker/ubuntu-host/entrypoint.sh; do bash -n "$f"; done` | Aucun message d'erreur | [**Réussi en CI**](https://github.com/K4ROUI/linux-infrastructure-automation-monitoring/actions/runs/43718378358) |
| Deux SSH par clés | `bash scripts/lab.sh up` | Ports 2221 et 2222 accessibles avec la clé locale | [**Réussi en CI**](https://github.com/K4ROUI/linux-infrastructure-automation-monitoring/actions/runs/43718378358) |
| Déploiement Ansible | `bash scripts/lab.sh provision` | Nginx configuré, page servie | [**Réussi en CI**](https://github.com/K4ROUI/linux-infrastructure-automation-monitoring/actions/runs/43718378358) |
| Ansible idempotent | Relancer `provision` | `changed=0` sur les deux hôtes | [**Réussi en CI**](https://github.com/K4ROUI/linux-infrastructure-automation-monitoring/actions/runs/43718378358) |
| API Prometheus et exporters | `bash scripts/lab.sh test` | 2 exporters `up=1` | [**Réussi en CI**](https://github.com/K4ROUI/linux-infrastructure-automation-monitoring/actions/runs/43718378358) |
| Sonde HTTP | `bash scripts/lab.sh test` | `probe_success=1` | [**Réussi en CI**](https://github.com/K4ROUI/linux-infrastructure-automation-monitoring/actions/runs/43718378358) |
| Grafana | `bash scripts/lab.sh test` | Base Grafana `ok` et dashboard provisionné | [**Réussi en CI**](https://github.com/K4ROUI/linux-infrastructure-automation-monitoring/actions/runs/43718378358) |
| Sauvegarde | `bash scripts/lab.sh backup` | Copie et SHA-256 identiques | [**Réussi en CI**](https://github.com/K4ROUI/linux-infrastructure-automation-monitoring/actions/runs/43718378358) |
| Restauration | `bash scripts/lab.sh restore ID` | Hash correct après restauration | [**Réussi en CI**](https://github.com/K4ROUI/linux-infrastructure-automation-monitoring/actions/runs/43718378358) |
| Incident Nginx | `incident` puis `check_alert.py --state firing` | Alerte active après temporisation | [**Réussi en CI**](https://github.com/K4ROUI/linux-infrastructure-automation-monitoring/actions/runs/43718378358) |
| Rétablissement | `recover` puis `check_alert.py --state resolved` | Alerte résolue | [**Réussi en CI**](https://github.com/K4ROUI/linux-infrastructure-automation-monitoring/actions/runs/43718378358) |

**Important :** les réussites du tableau proviennent de l'exécution GitHub Actions citée, pas d'une session Linux personnelle non documentée. Pour toute exécution locale, conserver séparément le résultat et les captures correspondantes.

## Vérifications manuelles à documenter

1. Capture Ansible `PLAY RECAP` de deux exécutions successives montrant l'idempotence.
2. Capture Grafana du dashboard avec les deux exporters et la sonde HTTP.
3. Capture de la panne : `probe_success = 0`, alerte active dans Prometheus/Alertmanager.
4. Capture après restauration : service HTTP de retour, alerte résolue.
5. ID de snapshot et résultat **SHA-256** d'une sauvegarde réellement effectuée.

Déposer uniquement des captures authentiques et masquer les secrets, identifiants et éventuelles données locales.

## Limites connues

- Hôtes Ubuntu simulés en **conteneurs**, non en VM ni matériel physique.
- Accès SSH sur loopback, pas de réseau d'entreprise.
- `sudo` sans mot de passe dans un environnement de test, donc **pas un niveau de durcissement production**.
- `node_exporter` voit potentiellement les métriques du noyau hôte, pas une attribution fine de ressources par conteneur.
- Alertmanager affiche les alertes mais n'envoie pas d'email/SMS (aucun destinataire configuré).
- Sauvegardes **déclenchées manuellement**, conservées sur un volume du même hôte Docker ; aucune sauvegarde distante/offsite.
- Le contrôle d'intégrité porte sur le fichier `index.html` et non tous les fichiers de tous les serveurs.
- Les résultats GitHub Actions cités ne prouvent que l'exécution CI sur un hôte Ubuntu partagé du runner ; ils ne démontrent pas de déploiement local ou de robustesse en production.
