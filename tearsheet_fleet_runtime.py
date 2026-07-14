#!/usr/bin/env python3
"""Canonical production runtime root for the TKP/TCP/AGM tearsheet fleet.

Single source of truth: ``tearsheet_fleet_runtime.json`` next to this module.

Refuses to resolve launch paths when the configured runtime root is the dirty
Tearsheet Generator checkout (active development workspace).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

_CONFIG_PATH = Path(__file__).resolve().parent / "tearsheet_fleet_runtime.json"


class DirtyRuntimeRootError(RuntimeError):
    """Raised when production fleet would launch from the dirty root checkout."""


def config_path() -> Path:
    return _CONFIG_PATH


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    cfg_path = path or _CONFIG_PATH
    with open(cfg_path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid tearsheet fleet runtime config: {cfg_path}")
    return data


def _norm(path: Path) -> Path:
    return path.expanduser().resolve()


def assert_not_dirty_root(runtime_root: Path, dirty_root: Path) -> None:
    runtime = _norm(runtime_root)
    dirty = _norm(dirty_root)
    if runtime == dirty:
        raise DirtyRuntimeRootError(
            "Refusing to start the production tearsheet fleet from the dirty "
            f"Tearsheet Generator checkout: {runtime}. "
            "Use the canonical live-deploy-main runtime root configured in "
            f"{_CONFIG_PATH}."
        )


def get_runtime_root(cfg: Optional[Mapping[str, Any]] = None) -> Path:
    data = dict(cfg) if cfg is not None else load_config()
    runtime = _norm(Path(str(data["runtime_root"])))
    dirty = _norm(Path(str(data["dirty_root"])))
    assert_not_dirty_root(runtime, dirty)
    if not runtime.is_dir():
        raise RuntimeError(f"Tearsheet fleet runtime root does not exist: {runtime}")
    if not (runtime / "tkp_ts.py").is_file():
        raise RuntimeError(
            f"Tearsheet fleet runtime root looks incomplete (missing tkp_ts.py): {runtime}"
        )
    return runtime


def get_dirty_root(cfg: Optional[Mapping[str, Any]] = None) -> Path:
    data = dict(cfg) if cfg is not None else load_config()
    return _norm(Path(str(data["dirty_root"])))


def fleet_bat_path(service_name: str, cfg: Optional[Mapping[str, Any]] = None) -> Path:
    data = dict(cfg) if cfg is not None else load_config()
    launchers: Mapping[str, Any] = data.get("client_launchers") or {}
    rel = launchers.get(service_name)
    if not rel:
        raise KeyError(f"No client launcher configured for service: {service_name}")
    root = get_runtime_root(data)
    bat = root / str(rel)
    if not bat.is_file():
        raise FileNotFoundError(f"Client launcher not found for {service_name}: {bat}")
    return bat


def fleet_service_folder(service_name: str, cfg: Optional[Mapping[str, Any]] = None) -> Path:
    data = dict(cfg) if cfg is not None else load_config()
    folders: Mapping[str, Any] = data.get("service_folders") or {}
    suffix = folders.get(service_name, "")
    root = get_runtime_root(data)
    if suffix:
        return root / str(suffix)
    return root


def apply_fleet_bat_overrides(
    bat_services: Dict[str, Dict[str, Any]],
    *,
    service_names: Optional[tuple[str, ...]] = None,
) -> None:
    """Rewrite bat_path for fleet services in-place using the canonical runtime."""
    names = service_names or (
        "TKP Tearsheet",
        "TCP Tearsheet",
        "Momentum Pacer Tearsheet",
    )
    cfg = load_config()
    for name in names:
        if name not in bat_services:
            continue
        bat_services[name]["bat_path"] = fleet_bat_path(name, cfg)
