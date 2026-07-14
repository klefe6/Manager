#!/usr/bin/env python3
"""Post-restart verification for TKP/TCP/AGM (no export, no row deletes)."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

LIVE = Path(r"C:\Coding Projects\Tearsheet Generator\.worktrees\live-deploy-main")
DIRTY = Path(r"C:\Coding Projects\Tearsheet Generator")
PORTS = {"TKP": 8301, "TCP": 8302, "AGM": 8304}
INGEST = {
    "TKP": "http://127.0.0.1:8301/api/uploader/ingest-daily-row",
    "TCP": "http://127.0.0.1:8302/api/uploader/ingest-daily-row",
    "AGM": "http://127.0.0.1:8304/api/uploader/ingest-daily-row",
}


def _cwd(pid: int) -> str:
    py = r"""
import ctypes
from ctypes import wintypes
import sys
pid = int(sys.argv[1])
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
ntdll = ctypes.WinDLL('ntdll', use_last_error=True)
class PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [('Reserved1', ctypes.c_void_p), ('PebBaseAddress', ctypes.c_void_p),
                ('Reserved2', ctypes.c_void_p * 2), ('UniqueProcessId', ctypes.c_void_p),
                ('Reserved3', ctypes.c_void_p)]
class UNICODE_STRING(ctypes.Structure):
    _fields_ = [('Length', wintypes.USHORT), ('MaximumLength', wintypes.USHORT),
                ('Buffer', ctypes.c_void_p)]
access = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
h = kernel32.OpenProcess(access, False, pid)
if not h:
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid)
if not h:
    print(''); sys.exit(0)
try:
    pbi = PROCESS_BASIC_INFORMATION()
    if ntdll.NtQueryInformationProcess(h, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), None) != 0:
        print(''); sys.exit(0)
    pp = ctypes.c_void_p(); nread = ctypes.c_size_t()
    if not kernel32.ReadProcessMemory(h, ctypes.c_void_p(pbi.PebBaseAddress + 0x20), ctypes.byref(pp), ctypes.sizeof(pp), ctypes.byref(nread)):
        print(''); sys.exit(0)
    us = UNICODE_STRING()
    if not kernel32.ReadProcessMemory(h, ctypes.c_void_p(pp.value + 0x38), ctypes.byref(us), ctypes.sizeof(us), ctypes.byref(nread)):
        print(''); sys.exit(0)
    buf = ctypes.create_unicode_buffer(max(us.MaximumLength // 2, 1))
    if not kernel32.ReadProcessMemory(h, ctypes.c_void_p(us.Buffer), buf, us.MaximumLength, ctypes.byref(nread)):
        print(''); sys.exit(0)
    print(buf.value)
finally:
    kernel32.CloseHandle(h)
"""
    r = subprocess.run(
        [sys.executable, "-c", py, str(pid)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return (r.stdout or "").strip()


def listener_pid(port: int) -> int | None:
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-NetTCPConnection -State Listen -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess"],
            text=True,
            timeout=30,
        ).strip()
        return int(out) if out.isdigit() else None
    except Exception:
        return None


def cmdline(pid: int) -> str:
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\").CommandLine"],
            text=True,
            timeout=30,
        )
        return (out or "").strip()
    except Exception:
        return ""


def http_status(url: str, data: bytes | None = None, headers: dict | None = None) -> int:
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as e:
        return int(e.code)
    except Exception:
        return -1


def wait_port(port: int, timeout: float = 120.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                return True
        except OSError:
            time.sleep(1)
    return False


def kill_port(port: int) -> None:
    pid = listener_pid(port)
    if pid:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=30)
        time.sleep(2)


def verify(label: str) -> dict:
    report = {"label": label, "ok": True, "services": {}}
    for name, port in PORTS.items():
        pid = listener_pid(port)
        cmd = cmdline(pid) if pid else ""
        cwd = _cwd(pid) if pid else ""
        root_ok = "live-deploy-main" in cmd or "live-deploy-main" in cwd
        dirty_bad = (
            str(DIRTY).lower() in cmd.lower()
            and "live-deploy-main" not in cmd.lower()
            and "live-deploy-main" not in cwd.lower()
        )
        ingest = http_status(
            INGEST[name],
            data=b'{"date":"2099-01-01","fields":{}}',
            headers={"Content-Type": "application/json"},
        )
        # AGM historically returns 403 when ingest env failed to load; accept only 401
        # (missing/invalid token) as proof that ingest is enabled + token configured.
        ingest_ok = ingest == 401
        health = http_status(f"http://127.0.0.1:{port}/")
        dbg = http_status(f"http://127.0.0.1:{port}/?__debugger__=yes&cmd=resource&f=style.css")
        # Dash apps return the app HTML (~5k) when debugger is off; Werkzeug CSS is different.
        body_len = 0
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/?__debugger__=yes&cmd=resource&f=style.css", timeout=10
            ) as resp:
                body_len = len(resp.read())
        except Exception:
            body_len = -1
        svc = {
            "pid": pid,
            "cmd": cmd,
            "cwd": cwd,
            "health": health,
            "ingest_no_auth": ingest,
            "debugger_probe_status": dbg,
            "debugger_body_len": body_len,
            "runtime_ok": bool(pid) and root_ok and not dirty_bad and health == 200 and ingest_ok,
        }
        if name == "TKP":
            # Debugger off => probe returns Dash HTML, not tiny CSS sheet.
            svc["debugger_disabled"] = body_len > 1000 or dbg != 200
            svc["runtime_ok"] = svc["runtime_ok"] and svc["debugger_disabled"]
        if name == "TCP":
            try:
                with urllib.request.urlopen("http://127.0.0.1:8302/healthz", timeout=10) as resp:
                    hz = json.loads(resp.read().decode("utf-8", errors="replace"))
                svc["healthz_debug"] = hz.get("debug")
                svc["runtime_ok"] = svc["runtime_ok"] and hz.get("debug") is False
            except Exception as e:
                svc["healthz_error"] = str(e)
                svc["runtime_ok"] = False
        report["services"][name] = svc
        if not svc["runtime_ok"]:
            report["ok"] = False
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "check"
    rep = verify(label)
    sys.exit(0 if rep["ok"] else 1)
