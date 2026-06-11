from __future__ import annotations

import subprocess
from pathlib import Path

from backend.platform.common import PlatformAdapter

SERVICE_NAME = "agentos"


class LinuxAdapter(PlatformAdapter):
    name = "linux"

    def get_service_path(self) -> Path:
        return Path(f"/etc/systemd/system/{SERVICE_NAME}.service")

    def get_log_dir(self) -> Path:
        return Path("/var/log/agentos")

    def install_service(self) -> bool:
        project_dir = self.get_project_dir()
        venv_python = self.get_venv_python()
        port = self.find_free_port()

        service_content = f"""[Unit]
Description=AgentOS — Agentic Operating System
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User={subprocess.getoutput('whoami')}
WorkingDirectory={project_dir}
ExecStart={venv_python} -m uvicorn backend.main:app --host 0.0.0.0 --port {port}
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        service_path = self.get_service_path()

        # Need sudo for /etc/systemd/system/
        tmp_path = Path(f"/tmp/{SERVICE_NAME}.service")
        tmp_path.write_text(service_content)
        subprocess.run(["sudo", "cp", str(tmp_path), str(service_path)], check=True)
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        subprocess.run(["sudo", "systemctl", "enable", SERVICE_NAME], check=True)
        subprocess.run(["sudo", "systemctl", "start", SERVICE_NAME], check=True)

        # Write port
        data_dir = self.get_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "port").write_text(str(port))

        return True

    def uninstall_service(self) -> bool:
        subprocess.run(["sudo", "systemctl", "stop", SERVICE_NAME], check=False)
        subprocess.run(["sudo", "systemctl", "disable", SERVICE_NAME], check=False)
        service_path = self.get_service_path()
        if service_path.exists():
            subprocess.run(["sudo", "rm", str(service_path)], check=False)
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=False)
        return True

    def start_service(self) -> bool:
        result = subprocess.run(["sudo", "systemctl", "start", SERVICE_NAME])
        return result.returncode == 0

    def stop_service(self) -> bool:
        result = subprocess.run(["sudo", "systemctl", "stop", SERVICE_NAME])
        return result.returncode == 0

    def is_service_running(self) -> bool:
        result = subprocess.run(
            ["systemctl", "is-active", SERVICE_NAME],
            capture_output=True, text=True,
        )
        return result.stdout.strip() == "active"

    def get_local_ip(self) -> str:
        try:
            result = subprocess.run(
                ["hostname", "-I"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip().split()[0]
        except Exception:
            pass
        return super().get_local_ip()
