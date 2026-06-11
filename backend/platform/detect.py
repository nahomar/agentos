from __future__ import annotations

import platform
import sys


def get_platform():
    """Detect the current platform and return the appropriate adapter."""
    system = platform.system().lower()

    if system == "darwin":
        from backend.platform.macos import MacOSAdapter
        return MacOSAdapter()
    elif system == "linux":
        from backend.platform.linux import LinuxAdapter
        return LinuxAdapter()
    else:
        from backend.platform.common import PlatformAdapter
        return PlatformAdapter()


def get_platform_name() -> str:
    return platform.system().lower()
