#!/usr/bin/env python3
"""Local strict dry-run ingest probe against loopback tearsheets (no Export All)."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

ENV_PATH = Path(r"C:\Coding Projects\Tearsheet Generator\.local_dev.env")

PROGRAMS = {
    "TKP": (
        "http://127.0.0.1:8301/api/uploader/ingest-daily-row",
        {
            "program": "TKP",
            "date": "2099-01-01",
            "source": "glenn_uploader_preflight",
            "dry_run": True,
            "stonex_nlv": 100000,
            "plus500_nlv": 50000,
            "cash_transfer": 0,
        },
    ),
    "TCP": (
        "http://127.0.0.1:8302/api/uploader/ingest-daily-row",
        {
            "program": "TCP",
            "date": "2099-01-01",
            "source": "glenn_uploader_preflight",
            "dry_run": True,
            "stonex_nlv": 100000,
            "cash_transfer": 0,
        },
    ),
    "AGM": (
        "http://127.0.0.1:8304/api/uploader/ingest-daily-row",
        {
            "program": "AGM",
            "date": "2099-01-01",
            "source": "glenn_uploader_preflight",
            "dry_run": True,
            "tradestation_nlv": 100000,
            "cash_transfer": 0,
            "fee": 0,
        },
    ),
}


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r'^set "([^=]+)=(.*)"$', line.strip())
        if m:
            env[m.group(1)] = m.group(2)
    return env


def main() -> int:
    env = load_env(ENV_PATH)
    token = env.get("GLENN_UPLOADER_INGEST_TOKEN", "")
    print(f"token_configured={bool(token)} token_len={len(token)}")
    print(f"enabled={env.get('GLENN_UPLOADER_INGEST_ENABLED')}")
    print(f"dry_run_allowed={env.get('GLENN_UPLOADER_INGEST_DRY_RUN_ALLOWED')}")
    ok = True
    for name, (url, payload) in PROGRAMS.items():
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Glenn-Uploader-Token": token,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.status
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            status = e.code
            data = json.loads(e.read().decode("utf-8", errors="replace") or "{}")
        accepted = data.get("accepted")
        dry = data.get("dry_run")
        msg = str(data.get("message") or "")[:160]
        print(
            f"{name}: http={status} accepted={accepted} dry_run={dry} "
            f"action={data.get('action')} msg={msg}"
        )
        if not (status == 200 and accepted is True and dry is True):
            ok = False
    print("STRICT_LOCAL", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
