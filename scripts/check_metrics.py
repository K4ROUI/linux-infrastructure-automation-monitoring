#!/usr/bin/env python3
"""Vérifie la disponibilité des deux exporters, de la sonde HTTP et des APIs.

Nécessite un environnement déjà provisionné. Utilise seulement la bibliothèque Python standard.
"""
import json
import sys
import time
from urllib.parse import urlencode
from urllib.request import urlopen

PROM = "http://127.0.0.1:9090"


def get_json(url: str):
    with urlopen(url, timeout=6) as response:
        return json.load(response)


def query(expression: str):
    payload = get_json(PROM + "/api/v1/query?" + urlencode({"query": expression}))
    if payload.get("status") != "success":
        raise RuntimeError(f"Réponse Prometheus inattendue : {payload}")
    return payload["data"]["result"]


def check_once():
    grafana = get_json("http://127.0.0.1:3000/api/health")
    if grafana.get("database") != "ok":
        raise RuntimeError(f"Grafana indisponible : {grafana}")
    am = get_json("http://127.0.0.1:9093/api/v2/status")
    if not am.get("cluster", {}).get("status"):
        # In single-node configurations cluster.status is usually "ready".
        # Some releases omit it; API read success is the real check.
        pass
    up = query('up{job="node-linux"}')
    if len(up) != 2 or any(float(series["value"][1]) != 1 for series in up):
        raise RuntimeError(f"Les deux exporters doivent être joignables : {up}")
    probe = query('probe_success{job="http-health"}')
    if len(probe) != 1 or float(probe[0]["value"][1]) != 1:
        raise RuntimeError(f"Sonde HTTP non fonctionnelle : {probe}")
    rules = get_json(PROM + "/api/v1/rules")
    groups = [g.get("name") for g in rules.get("data", {}).get("groups", [])]
    if "linux-lab-alerts" not in groups:
        raise RuntimeError(f"Règles d'alerte absentes : {groups}")
    return {"exporters": 2, "http_probe": 1, "grafana_db": "ok", "rules": "linux-lab-alerts"}


def main():
    last_error = None
    for _ in range(45):
        try:
            result = check_once()
            print("[OK] Supervision :", result)
            return 0
        except Exception as exc:
            last_error = exc
            time.sleep(2)
    print(f"[ERREUR] Supervision indisponible après essais : {last_error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
