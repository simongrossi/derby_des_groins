#!/usr/bin/env python3
"""Vérifie les collisions de routes Flask (endpoint + méthode + URL)."""

from collections import defaultdict
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app


def main():
    collisions = defaultdict(list)

    for rule in app.url_map.iter_rules():
        methods = sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"})
        key = (tuple(methods), rule.rule)
        collisions[key].append(rule.endpoint)

    duplicate_entries = {
        key: endpoints
        for key, endpoints in collisions.items()
        if len(endpoints) > 1
    }

    if duplicate_entries:
        print("❌ Duplicate Flask routes detected:")
        for (methods, route), endpoints in sorted(duplicate_entries.items()):
            print(f"  {','.join(methods)} {route}: {endpoints}")
        raise SystemExit(1)

    print("✅ No duplicate Flask routes found.")


if __name__ == "__main__":
    main()
