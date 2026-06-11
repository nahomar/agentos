from __future__ import annotations

import os
import subprocess
from pathlib import Path

from backend.platform.common import PlatformAdapter

PLIST_LABEL = "com.agentos.daemon"


class MacOSAdapter(PlatformAdapter):
    name = "macos"

    def get_plist_path(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"

    def install_service(self) -> bool:
        project_dir = self.get_project_dir()
        venv_python = self.get_venv_python()
        port = self.find_free_port()
        log_file = self.get_log_file()
        error_log = self.get_error_log_file()

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{PLIST_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{venv_python}</string>
    <string>-m</string>
    <string>uvicorn</string>
    <string>backend.main:app</string>
    <string>--host</string>
    <string>0.0.0.0</string>
    <string>--port</string>
    <string>{port}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>{project_dir}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{log_file}</string>
  <key>StandardErrorPath</key>
  <string>{error_log}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
    <key>PATH</key>
    <string>{venv_python.parent}:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
</dict>
</plist>
"""
        plist_path = self.get_plist_path()
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        plist_path.write_text(plist_content)

        # Write port to data dir
        data_dir = self.get_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "port").write_text(str(port))

        # Load the LaunchAgent
        subprocess.run(["launchctl", "load", "-w", str(plist_path)], check=True)
        return True

    def uninstall_service(self) -> bool:
        plist_path = self.get_plist_path()
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", "-w", str(plist_path)], check=False)
            plist_path.unlink()
        return True

    def start_service(self) -> bool:
        plist_path = self.get_plist_path()
        if plist_path.exists():
            subprocess.run(["launchctl", "load", "-w", str(plist_path)], check=True)
            return True
        return False

    def stop_service(self) -> bool:
        plist_path = self.get_plist_path()
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", str(plist_path)], check=False)
            return True
        return False

    def is_service_running(self) -> bool:
        result = subprocess.run(
            ["launchctl", "list", PLIST_LABEL],
            capture_output=True, text=True,
        )
        return result.returncode == 0

    def get_local_ip(self) -> str:
        try:
            result = subprocess.run(
                ["ipconfig", "getifaddr", "en0"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return super().get_local_ip()
