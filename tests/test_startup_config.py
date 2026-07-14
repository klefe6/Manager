"""
Startup configuration contract tests.

These guard the two things that actually broke: a website (Glenn Uploader) that
was never added to automatic startup, and a multi-process service being reported
as healthy when only half of it was up.

Everything here is pure unit testing of the configuration and health logic - no
live ports are touched, so the suite is safe to run while the fleet is serving.
"""

import json
import subprocess
from pathlib import Path

import pytest

import generate_startup_contract
import launch_all_services as launcher
import service_config as cfg


GLENN = "Glenn Uploader"
GLENN_FRONTEND_PORT = 5173
GLENN_BACKEND_PORT = 8091
STAFF_PORTS = (8321, 8322, 8324)


# ─────────────────────────────────────────────────────────────────────────────
# 1-2. Glenn is in the canonical startup configuration, via the right launcher
# ─────────────────────────────────────────────────────────────────────────────


def test_glenn_is_in_the_canonical_startup_config():
    """The regression that started all this: Glenn was missing from startup."""
    assert GLENN in cfg.BAT_SERVICES, (
        "Glenn Uploader is not in BAT_SERVICES, so it will not start at sign-in"
    )
    assert cfg.BAT_SERVICES[GLENN].get("auto_start", True) is not False


def test_glenn_invokes_the_expected_launcher():
    bat = cfg.BAT_SERVICES[GLENN]["bat_path"]
    assert bat.name == "reboot_glenn_uploader.bat"
    assert bat.parent.name == "Tearsheet Generator"
    assert bat.exists(), f"Glenn launcher does not exist on disk: {bat}"


def test_glenn_is_launched_by_the_master_sequence_not_just_the_dashboard():
    """Glenn must be reachable from the launcher's dashboard coverage map."""
    assert launcher.DEBUG_SITE_LAUNCH_TARGETS[GLENN] == [f"BAT:{GLENN}"]
    assert f"BAT:{GLENN}" in launcher._launch_registry()


# ─────────────────────────────────────────────────────────────────────────────
# 3-6. Health model: full / partial / offline
# ─────────────────────────────────────────────────────────────────────────────


def test_glenn_requires_both_ports_for_full_health():
    ports = cfg.service_health_ports(cfg.BAT_SERVICES[GLENN])
    assert sorted(ports) == sorted([GLENN_BACKEND_PORT, GLENN_FRONTEND_PORT])


def test_both_ports_up_is_online():
    status = {GLENN_BACKEND_PORT: True, GLENN_FRONTEND_PORT: True}
    assert cfg.classify_port_health(status) == cfg.HEALTH_ONLINE


def test_backend_only_is_partial_not_online():
    """The exact live state found during the audit: 8091 up, 5173 dead."""
    status = {GLENN_BACKEND_PORT: True, GLENN_FRONTEND_PORT: False}
    assert cfg.classify_port_health(status) == cfg.HEALTH_PARTIAL
    assert cfg.classify_port_health(status) != cfg.HEALTH_ONLINE


def test_frontend_only_is_partial_not_online():
    status = {GLENN_BACKEND_PORT: False, GLENN_FRONTEND_PORT: True}
    assert cfg.classify_port_health(status) == cfg.HEALTH_PARTIAL
    assert cfg.classify_port_health(status) != cfg.HEALTH_ONLINE


def test_neither_port_is_offline():
    status = {GLENN_BACKEND_PORT: False, GLENN_FRONTEND_PORT: False}
    assert cfg.classify_port_health(status) == cfg.HEALTH_OFFLINE


def test_single_port_service_can_never_be_partial():
    """Backward compatibility: existing single-port services keep binary health."""
    assert cfg.classify_port_health({8301: True}) == cfg.HEALTH_ONLINE
    assert cfg.classify_port_health({8301: False}) == cfg.HEALTH_OFFLINE


def test_health_ports_falls_back_to_single_port_key():
    assert cfg.service_health_ports({"port": 8301}) == [8301]
    assert cfg.service_health_ports({}) == []


# ─────────────────────────────────────────────────────────────────────────────
# 7. A Glenn failure must not take unrelated services down with it
# ─────────────────────────────────────────────────────────────────────────────


def test_glenn_failure_does_not_abort_unrelated_services():
    """One exploding service must not prevent TKP/TCP/AGM/Y&Q from launching."""
    attempted = []

    def flaky_launcher(name, config):
        attempted.append(name)
        if name == GLENN:
            raise RuntimeError("simulated Glenn launcher explosion")
        return object()  # stand-in for a live Popen

    items = {
        GLENN: cfg.BAT_SERVICES[GLENN],
        "TKP Tearsheet": cfg.BAT_SERVICES["TKP Tearsheet"],
        "TCP Tearsheet": cfg.BAT_SERVICES["TCP Tearsheet"],
        "Y&Q Tearsheet": cfg.BAT_SERVICES["Y&Q Tearsheet"],
        "AGM Allocation": cfg.BAT_SERVICES["AGM Allocation"],
    }
    all_services = {}
    failed = []

    launcher._launch_phase_items("TEST", items, flaky_launcher, all_services, failed)

    assert set(attempted) == set(items)
    for survivor in ("TKP Tearsheet", "TCP Tearsheet", "Y&Q Tearsheet", "AGM Allocation"):
        assert survivor in all_services, f"{survivor} did not launch after Glenn failed"
    assert GLENN in failed
    assert GLENN not in all_services


def test_glenn_failure_returning_none_is_recorded_as_failed():
    def none_launcher(name, config):
        return None if name == GLENN else object()

    all_services, failed = {}, []
    launcher._launch_phase_items(
        "TEST",
        {GLENN: cfg.BAT_SERVICES[GLENN], "TKP Tearsheet": cfg.BAT_SERVICES["TKP Tearsheet"]},
        none_launcher,
        all_services,
        failed,
    )
    assert GLENN in failed
    assert "TKP Tearsheet" in all_services


# ─────────────────────────────────────────────────────────────────────────────
# 8. Existing services keep their current launcher and port behaviour
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name, port, bat_name",
    [
        ("TKP Tearsheet", 8301, "reboot_tkp_ts.bat"),
        ("TCP Tearsheet", 8302, "reboot_tcp_ts.bat"),
        ("Y&Q Tearsheet", 8303, "reboot_yq_ts.bat"),
        ("Momentum Pacer Tearsheet", 8304, "reboot_mp_ts.bat"),
        ("AGM Allocation", 8511, "reboot_agm_allocation.bat"),
    ],
)
def test_existing_bat_services_unchanged(name, port, bat_name):
    entry = cfg.BAT_SERVICES[name]
    assert entry["port"] == port
    assert entry["bat_path"].name == bat_name
    # No health_ports key added => single-port semantics preserved exactly.
    assert cfg.service_health_ports(entry) == [port]


@pytest.mark.parametrize(
    "name",
    ["TKP Tearsheet", "TCP Tearsheet", "Momentum Pacer Tearsheet"],
)
def test_tearsheet_fleet_uses_live_deploy_runtime(name):
    bat = cfg.BAT_SERVICES[name]["bat_path"]
    assert "live-deploy-main" in str(bat)
    assert bat.is_file()
    assert cfg.get_runtime_root().name == "live-deploy-main"


def test_debug_dashboard_still_owns_8006():
    debug = cfg.DASH_APPS["Debug Page"]
    assert debug["port"] == 8006
    assert debug["script_path"].name == "debug.py"


def test_agm_card_ports_share_one_process():
    """AGM Client/Admin/Portal are routes on ONE process, not three services."""
    targets = {
        launcher.DEBUG_SITE_LAUNCH_TARGETS[card][0]
        for card in ("AGM Client", "AGM Admin", "AGM Portal")
    }
    assert targets == {"BAT:Momentum Pacer Tearsheet"}


# ─────────────────────────────────────────────────────────────────────────────
# 9. Staff/admin ports stay manual-only
# ─────────────────────────────────────────────────────────────────────────────


def test_staff_ports_are_declared_manual_only():
    assert set(cfg.MANUAL_ONLY_PORTS) == set(STAFF_PORTS)


@pytest.mark.parametrize("staff_port", STAFF_PORTS)
def test_no_launcher_config_references_a_staff_port(staff_port):
    for key, entry in launcher._launch_registry().items():
        assert staff_port not in cfg.service_health_ports(entry), (
            f"{key} would auto-start manual-only staff port {staff_port}"
        )


def test_coverage_check_rejects_a_staff_port_sneaking_into_startup(monkeypatch):
    """If someone wires 8324 into a launcher config, startup must fail loudly."""
    poisoned = dict(cfg.BAT_SERVICES)
    poisoned["Rogue Staff Service"] = {
        "bat_path": cfg.BAT_SERVICES[GLENN]["bat_path"],
        "port": 8324,
        "python_exe": None,
    }
    monkeypatch.setattr(cfg, "BAT_SERVICES", poisoned)
    monkeypatch.setattr(launcher, "BAT_SERVICES", poisoned)

    errors, _ = launcher.verify_dashboard_launch_coverage()
    assert any("8324" in e and "manual-only" in e for e in errors), errors


# ─────────────────────────────────────────────────────────────────────────────
# 10. Coverage validation catches a card with no startup decision
# ─────────────────────────────────────────────────────────────────────────────


def test_coverage_check_catches_a_card_with_no_launcher(monkeypatch):
    monkeypatch.setitem(
        launcher.DEBUG_SITE_LAUNCH_TARGETS, "Brand New Card", ["BAT:Does Not Exist"]
    )
    errors, _ = launcher.verify_dashboard_launch_coverage()
    assert any("Brand New Card" in e for e in errors), errors


def test_coverage_check_catches_a_launcher_pointing_at_a_missing_file(monkeypatch):
    broken = dict(cfg.BAT_SERVICES)
    broken[GLENN] = {
        **cfg.BAT_SERVICES[GLENN],
        "bat_path": Path(r"C:\Coding Projects\Tearsheet Generator\does_not_exist.bat"),
    }
    monkeypatch.setattr(launcher, "BAT_SERVICES", broken)

    errors, _ = launcher.verify_dashboard_launch_coverage()
    assert any(GLENN in e and "missing file" in e for e in errors), errors


def test_real_configuration_has_no_coverage_errors():
    errors, _ = launcher.verify_dashboard_launch_coverage()
    assert errors == [], f"Startup configuration has coverage errors: {errors}"


# ─────────────────────────────────────────────────────────────────────────────
# Source-of-truth contract stays in sync
# ─────────────────────────────────────────────────────────────────────────────


def test_committed_contract_is_not_stale():
    """startup_contract.json must match service_config.py exactly."""
    committed = generate_startup_contract.CONTRACT_PATH.read_text(encoding="utf-8")
    assert committed == generate_startup_contract.render(), (
        "startup_contract.json is stale - run: python generate_startup_contract.py"
    )


def test_contract_exposes_glenn_with_both_ports():
    contract = json.loads(generate_startup_contract.render())
    glenn = contract["services"][GLENN]
    assert sorted(glenn["health_ports"]) == sorted([GLENN_BACKEND_PORT, GLENN_FRONTEND_PORT])
    assert glenn["launcher"].endswith("reboot_glenn_uploader.bat")


def test_contract_marks_staff_ports_manual_only():
    contract = json.loads(generate_startup_contract.render())
    assert sorted(contract["manual_only_ports"]) == sorted(str(p) for p in STAFF_PORTS)
    for entry in contract["services"].values():
        for staff_port in STAFF_PORTS:
            assert staff_port not in entry["health_ports"]
