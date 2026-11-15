# Plan de validation, preuve et état actuel

## Ce que les fichiers doivent permettre de tester

| Vérification | Méthode | Résultat attendu | Résultat réel |
| --- | --- | --- | --- |
| Scripts et configurations corrects | `python3 -m unittest discover -s tests -v` | Tests statiques réussis | À exécuter / voir sortie CI |
| Syntaxe Bash | `for f in scripts/*.sh docker/ubuntu-host/entrypoint.sh; do bash -n "$f"; done` | Aucun message d'erreur | À exécuter / voir sortie CI |
| Deux SSH par clés | `bash scripts/lab.sh up` | Ports 2221 et 2222 accessibles avec la clé locale | À exécuter / voir sortie CI |
| Déploiement Ansible | `bash scripts/lab.sh provision` | Nginx configuré, page servie | À exécuter / voir sortie CI |
| Ansible idempotent | Relancer `provision` | `changed=0` sur les deux hôtes | À exécuter / voir sortie CI |
| API Prometheus et exporters | `bash scripts/lab.sh test` | 2 exporters `up=1` | À exécuter / voir sortie CI |
| Sonde HTTP | `bash scripts/lab.sh test` | `probe_success=1` | À exécuter / voir sortie CI |
| Grafana | `bash scripts/lab.sh test` | Base Grafana `ok` et dashboard provisionné | À exécuter / voir sortie CI |
| Sauvegarde | `bash scripts/lab.sh backup` | Copie et SHA-256 identiques | À exécuter / voir sortie CI |
| Restauration | `bash scripts/lab.sh restore ID` | Hash correct après restauration | À exécuter / voir sortie CI |
| Incident Nginx | `incident` puis `check_alert.py --state firing` | Alerte active après temporisation | À exécuter / voir sortie CI |
| Rétablissement | `recover` puis `check_alert.py --state resolved` | Alerte résolue | À exécuter / voir sortie CI |

**Important :** ce tableau est un **protocole de validation**, pas un journal de résultats fabriqués. Remplacer « À exécuter » uniquement après avoir conservé une sortie terminal ou un lien GitHub Actions réel.

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
- Sans publication GitHub et exécution CI, ne pas revendiquer d'intégration validée.
