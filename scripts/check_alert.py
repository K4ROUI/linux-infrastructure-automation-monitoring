#!/usr/bin/env python3
"""Attendre la présence (ou l'absence) d'une alerte Prometheus précise."""
import argparse
import json
import sys
import time
from urllib.request import urlopen


def is_firing():
    with urlopen('http://127.0.0.1:9090/api/v1/alerts', timeout=6) as response:
        data = json.load(response)
    return any(a.get('labels', {}).get('alertname') == 'WebServiceUnavailable'
               and a.get('state') == 'firing'
               for a in data.get('data', {}).get('alerts', []))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', choices=['firing', 'resolved'], required=True)
    parser.add_argument('--timeout', type=int, default=85)
    args = parser.parse_args()
    expected = args.state == 'firing'
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        try:
            if is_firing() == expected:
                print(f'[OK] WebServiceUnavailable état attendu : {args.state}')
                return 0
        except Exception:
            pass
        time.sleep(3)
    print(f'[ERREUR] Alerte ne passe pas à l’état {args.state}', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
