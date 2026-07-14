#!/usr/bin/env python3
"""Tests for canonical tearsheet fleet runtime root resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import tearsheet_fleet_runtime as tfr


def test_get_runtime_root_points_at_live_deploy():
    root = tfr.get_runtime_root()
    assert root.name == "live-deploy-main"
    assert (root / "tkp_ts.py").is_file()
    assert root != tfr.get_dirty_root()


def test_fleet_bat_paths_live_under_runtime_root():
    root = tfr.get_runtime_root()
    for name, bat_name in (
        ("TKP Tearsheet", "reboot_tkp_ts.bat"),
        ("TCP Tearsheet", "reboot_tcp_ts.bat"),
        ("Momentum Pacer Tearsheet", "reboot_mp_ts.bat"),
        ("AGM Tearsheet", "reboot_mp_ts.bat"),
    ):
        bat = tfr.fleet_bat_path(name)
        assert bat.parent == root
        assert bat.name == bat_name
        assert bat.is_file()


def test_assert_not_dirty_root_refuses_dirty_checkout():
    dirty = Path(r"C:\Coding Projects\Tearsheet Generator")
    with pytest.raises(tfr.DirtyRuntimeRootError):
        tfr.assert_not_dirty_root(dirty, dirty)


def test_get_runtime_root_refuses_config_pointing_at_dirty():
    dirty = Path(r"C:\Coding Projects\Tearsheet Generator")
    cfg = {
        "runtime_root": str(dirty),
        "dirty_root": str(dirty),
        "client_launchers": {},
    }
    with pytest.raises(tfr.DirtyRuntimeRootError):
        tfr.get_runtime_root(cfg)


def test_service_config_uses_live_deploy_bats():
    from service_config import BAT_SERVICES, _TEARSHEET_RUNTIME_ROOT

    assert _TEARSHEET_RUNTIME_ROOT.name == "live-deploy-main"
    for name in ("TKP Tearsheet", "TCP Tearsheet", "Momentum Pacer Tearsheet"):
        bat = Path(BAT_SERVICES[name]["bat_path"])
        assert "live-deploy-main" in str(bat)
        assert bat.is_file()
