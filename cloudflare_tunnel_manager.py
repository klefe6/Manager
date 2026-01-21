#!/usr/bin/env python3
"""
Cloudflare Tunnel Manager

Manages Cloudflare Tunnel lifecycle alongside service launcher.
Handles tunnel start/stop and health monitoring.
"""

import subprocess
import os
import sys
import time
import json
import shutil
from pathlib import Path
from typing import Optional, Dict

# Try to import yaml, fallback to manual parsing if not available
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

BASE_DIR = Path(r"C:\Program Files\Coding Projects")
CONFIG_FILE = BASE_DIR / "Manager" / "cloudflare_tunnel_config.yaml"
TUNNEL_LOG_DIR = BASE_DIR / "Manager" / "logs"
TUNNEL_LOG_DIR.mkdir(parents=True, exist_ok=True)


class CloudflareTunnelManager:
    """Manages Cloudflare Tunnel process."""
    
    def __init__(self, config_file: Path = None):
        """Initialize tunnel manager."""
        self.config_file = config_file or CONFIG_FILE
        self.tunnel_process: Optional[subprocess.Popen] = None
        self.tunnel_name: Optional[str] = None
        self.tunnel_id: Optional[str] = None
        
        # Check if cloudflared is installed
        self.cloudflared_path = shutil.which("cloudflared")
        if not self.cloudflared_path:
            # Try common Windows locations
            common_paths = [
                r"C:\Program Files\Cloudflare\cloudflared.exe",
                r"C:\Program Files (x86)\Cloudflare\cloudflared.exe",
                os.path.expanduser(r"~\AppData\Local\cloudflared\cloudflared.exe"),
            ]
            for path in common_paths:
                if Path(path).exists():
                    self.cloudflared_path = path
                    break
        
        if not self.cloudflared_path:
            raise FileNotFoundError(
                "cloudflared not found. Install from: "
                "https://github.com/cloudflare/cloudflared/releases"
            )
    
    def load_config(self) -> Dict:
        """Load tunnel configuration from YAML."""
        if not self.config_file.exists():
            return {}
        
        try:
            if HAS_YAML:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
            else:
                # Fallback: simple YAML parsing for basic config
                config = self._parse_simple_yaml()
            
            # Extract tunnel ID from config
            self.tunnel_id = config.get('tunnel', '').strip()
            if self.tunnel_id.startswith('<'):
                # Placeholder
                if self.tunnel_id.startswith('<YOUR_TUNNEL_ID>'):
                    return {}
            
            return config
        except Exception as e:
            print(f"[WARN] Failed to load tunnel config: {e}")
            return {}
    
    def _parse_simple_yaml(self) -> Dict:
        """Simple YAML parser for basic tunnel config (fallback)."""
        config = {}
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            current_key = None
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if key == 'tunnel':
                        config['tunnel'] = value
                    elif key == 'credentials-file':
                        config['credentials-file'] = value
        except Exception:
            pass
        
        return config
    
    def is_tunnel_configured(self) -> bool:
        """Check if tunnel is properly configured."""
        config = self.load_config()
        if not config:
            return False
        
        tunnel_id = config.get('tunnel', '').strip()
        if not tunnel_id or tunnel_id.startswith('<'):
            return False
        
        # Check if credentials file exists
        creds_file = config.get('credentials-file', '')
        if creds_file and Path(creds_file).exists():
            return True
        
        # Try default location
        default_creds = Path.home() / ".cloudflared" / f"{tunnel_id}.json"
        return default_creds.exists()
    
    def get_tunnel_name(self) -> Optional[str]:
        """Get tunnel name from Cloudflare (requires listing tunnels)."""
        try:
            result = subprocess.run(
                [self.cloudflared_path, "tunnel", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Parse output to find tunnel name by ID
                lines = result.stdout.split('\n')
                for line in lines[1:]:  # Skip header
                    if self.tunnel_id and self.tunnel_id in line:
                        parts = line.split()
                        if len(parts) > 0:
                            return parts[0]
        except Exception:
            pass
        
        return None
    
    def start_tunnel(self) -> bool:
        """Start Cloudflare Tunnel."""
        if not self.is_tunnel_configured():
            print("[WARN] Cloudflare Tunnel not configured. Skipping.")
            print("[INFO] Run setup_cloudflare_tunnel.ps1 to configure.")
            return False
        
        if self.tunnel_process and self.tunnel_process.poll() is None:
            print("[INFO] Cloudflare Tunnel already running")
            return True
        
        config = self.load_config()
        self.tunnel_id = config.get('tunnel', '').strip()
        self.tunnel_name = self.get_tunnel_name() or self.tunnel_id
        
        print(f"[LAUNCH] Starting Cloudflare Tunnel: {self.tunnel_name}")
        
        # Log file
        log_file = TUNNEL_LOG_DIR / f"cloudflare_tunnel_{int(time.time())}.log"
        
        try:
            # Start tunnel using config file
            self.tunnel_process = subprocess.Popen(
                [
                    self.cloudflared_path,
                    "tunnel",
                    "--config", str(self.config_file),
                    "run"
                ],
                stdout=open(log_file, 'w', encoding='utf-8'),
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
            )
            
            # Give it a moment to start
            time.sleep(2)
            
            if self.tunnel_process.poll() is None:
                print(f"[OK] Cloudflare Tunnel started (PID: {self.tunnel_process.pid})")
                print(f"[INFO] Logs: {log_file}")
                return True
            else:
                print(f"[ERROR] Tunnel process died immediately (exit code: {self.tunnel_process.returncode})")
                print(f"[INFO] Check logs: {log_file}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Failed to start tunnel: {e}")
            return False
    
    def stop_tunnel(self):
        """Stop Cloudflare Tunnel."""
        if self.tunnel_process and self.tunnel_process.poll() is None:
            print(f"[STOP] Stopping Cloudflare Tunnel (PID: {self.tunnel_process.pid})")
            try:
                import psutil
                proc = psutil.Process(self.tunnel_process.pid)
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                    print("[OK] Tunnel stopped gracefully")
                except psutil.TimeoutExpired:
                    proc.kill()
                    print("[WARN] Tunnel force-killed")
            except Exception as e:
                print(f"[ERROR] Error stopping tunnel: {e}")
            finally:
                self.tunnel_process = None
        else:
            print("[INFO] Tunnel not running")
    
    def is_running(self) -> bool:
        """Check if tunnel is running."""
        return (
            self.tunnel_process is not None and
            self.tunnel_process.poll() is None
        )


def get_tunnel_manager() -> Optional[CloudflareTunnelManager]:
    """Get tunnel manager instance."""
    try:
        return CloudflareTunnelManager()
    except FileNotFoundError as e:
        print(f"[WARN] {e}")
        return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage Cloudflare Tunnel")
    parser.add_argument("action", choices=["start", "stop", "status"], help="Action to perform")
    
    args = parser.parse_args()
    
    manager = get_tunnel_manager()
    if not manager:
        sys.exit(1)
    
    if args.action == "start":
        manager.start_tunnel()
        if manager.is_running():
            print("\n[INFO] Tunnel is running. Press Ctrl+C to stop.")
            try:
                while True:
                    time.sleep(60)
            except KeyboardInterrupt:
                manager.stop_tunnel()
    elif args.action == "stop":
        manager.stop_tunnel()
    elif args.action == "status":
        if manager.is_running():
            print("[OK] Tunnel is running")
        else:
            print("[INFO] Tunnel is not running")
            if manager.is_tunnel_configured():
                print("[INFO] Tunnel is configured. Run 'start' to launch.")
            else:
                print("[WARN] Tunnel is not configured. Run setup_cloudflare_tunnel.ps1")
