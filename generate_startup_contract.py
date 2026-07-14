#!/usr/bin/env python3
"""
Regenerate startup_contract.json from service_config.py.

The contract is the source of truth shared with the Service Dashboard
(HomePage/debug.py), so that ports and launcher paths live in one place only.

Run this after changing any service definition:

    python generate_startup_contract.py

tests/test_startup_config.py fails if the committed contract has gone stale.
"""

import json
from pathlib import Path

from service_config import export_startup_contract

CONTRACT_PATH = Path(__file__).with_name("startup_contract.json")


def render() -> str:
    """Deterministic JSON so a stale contract shows up as a real diff."""
    return json.dumps(export_startup_contract(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    CONTRACT_PATH.write_text(render(), encoding="utf-8")
    print(f"[OK] wrote {CONTRACT_PATH}")


if __name__ == "__main__":
    main()
