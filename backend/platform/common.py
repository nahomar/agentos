from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Optional


class PlatformAdapter:
    """Base platform adapter. Subclassed for macOS/Linux/Windows."""

    name = "generic"

    def get_project_dir(self) -> Path:
        return Path(__file__).parent.parent.parent

    def get_data_dir(self) -> Path:
        return self.get_project_dir() / "data"

    def get_config_dir(self) -> Path:
        return self.get_project_dir()

    def get_log_dir(self) -> Path:
        return Path("/tmp")

    def get_venv_python(self) -> Path:
        return self.get_project_dir() / ".venv" / "bin" / "python3"

    def get_local_ip(self) -> str:
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "localhost"

    def install_service(self) -> bool:
        raise NotImplementedError(f"Service install not implemented for {self.name}")

    def uninstall_service(self) -> bool:
        raise NotImplementedError(f"Service uninstall not implemented for {self.name}")

    def start_service(self) -> bool:
        raise NotImplementedError

    def stop_service(self) -> bool:
        raise NotImplementedError

    def restart_service(self) -> bool:
        self.stop_service()
        return self.start_service()

    def is_service_running(self) -> bool:
        pid_file = self.get_data_dir() / "agentos.pid"
        if not pid_file.exists():
            return False
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)  # Check if process exists
            return True
        except (ProcessLookupError, ValueError):
            return False

    def get_log_file(self) -> Path:
        return self.get_log_dir() / "agentos.log"

    def get_error_log_file(self) -> Path:
        return self.get_log_dir() / "agentos-error.log"

    def get_system_info(self) -> dict:
        return {
            "platform": self.name,
            "os": platform.system(),
            "os_version": platform.version(),
            "arch": platform.machine(),
            "python": platform.python_version(),
            "hostname": platform.node(),
        }

    def find_free_port(self, start: int = 8000, end: int = 8010) -> int:
        import socket
        for port in range(start, end + 1):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(("0.0.0.0", port))
                s.close()
                return port
            except OSError:
                continue
        raise RuntimeError(f"No free port found in range {start}-{end}")
