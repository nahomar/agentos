from __future__ import annotations

"""AgentOS CLI — manage the agentic operating system."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent


def _get_platform():
    from backend.platform.detect import get_platform
    return get_platform()


def _get_port() -> int:
    port_file = PROJECT_DIR / "data" / "port"
    if port_file.exists():
        return int(port_file.read_text().strip())
    return 8000


def _api(path: str, method: str = "GET", data: dict = None):
    import httpx
    url = f"http://localhost:{_get_port()}{path}"
    try:
        if method == "GET":
            r = httpx.get(url, timeout=5)
        else:
            r = httpx.post(url, json=data, timeout=30)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def cmd_install(args):
    plat = _get_platform()
    try:
        plat.install_service()
        ip = plat.get_local_ip()
        port = _get_port()
        print(f"\n  ✓ AgentOS daemon installed and running")
        print(f"  Open: http://{ip}:{port}\n")
    except Exception as e:
        print(f"  ✗ Install failed: {e}")
        print(f"  Try: ./install/install.sh")


def cmd_uninstall(args):
    plat = _get_platform()
    try:
        plat.uninstall_service()
        print("  ✓ AgentOS daemon removed")
    except Exception as e:
        print(f"  ✗ Uninstall failed: {e}")


def cmd_start(args):
    plat = _get_platform()
    try:
        plat.start_service()
        print("  ✓ AgentOS started")
    except Exception as e:
        # Fallback: start directly
        print(f"  Starting directly...")
        venv = PROJECT_DIR / ".venv" / "bin" / "python3"
        port = _get_port()
        os.execv(str(venv), [str(venv), "-m", "uvicorn", "backend.main:app",
                             "--host", "0.0.0.0", "--port", str(port)])


def cmd_stop(args):
    plat = _get_platform()
    try:
        plat.stop_service()
        print("  ✓ AgentOS stopped")
    except Exception as e:
        print(f"  ✗ Stop failed: {e}")


def cmd_restart(args):
    plat = _get_platform()
    plat.stop_service()
    plat.start_service()
    print("  ✓ AgentOS restarted")


def cmd_logs(args):
    plat = _get_platform()
    log_file = plat.get_log_file()
    if plat.name == "linux":
        os.execlp("journalctl", "journalctl", "-u", "agentos", "-f")
    elif log_file.exists():
        os.execlp("tail", "tail", "-f", str(log_file))
    else:
        print(f"  No log file found at {log_file}")


def cmd_status(args):
    health = _api("/api/health")
    if "error" in health:
        print(f"\n  ✗ AgentOS is not running ({health['error']})\n")
        return

    kernel = _api("/api/kernel/status")

    print(f"\n  AgentOS v{kernel.get('version', '?')} \"{kernel.get('codename', '?')}\"")
    print(f"  {'─'*44}")
    print(f"  Agents:      {health.get('agents', 0)} ({health.get('active', 0)} active)")
    print(f"  Capabilities: {health.get('capabilities', 0)}")
    print(f"  Rules:        {health.get('rules', 0)}")
    print(f"  Bus Actions:  {health.get('semantic_bus_actions', 0)}")
    print(f"  Bus Apps:     {health.get('semantic_bus_apps', 0)}")
    print(f"  Safety Rules: {health.get('verification_rules', 0)}")
    print(f"  AI Brain:     {health.get('ai_brain', '?')}")

    wd = kernel.get("watchdog", {})
    print(f"  Watchdog:     {wd.get('healthy', 0)}/{wd.get('agents_monitored', 0)} healthy")

    plat = _get_platform()
    ip = plat.get_local_ip()
    port = _get_port()
    print(f"\n  Access: http://{ip}:{port}\n")


def cmd_list(args):
    agents = _api("/api/agents")
    if isinstance(agents, dict) and "error" in agents:
        print(f"  Error: {agents['error']}")
        return
    print(f"\n  {'Emoji':6s} {'Name':14s} {'Status':10s} Task")
    print(f"  {'─'*6} {'─'*14} {'─'*10} {'─'*30}")
    for a in agents:
        print(f"  {a['emoji']:6s} {a['name']:14s} {a['status']:10s} {a.get('current_task','')[:30]}")
    print(f"\n  {len(agents)} agents\n")


def cmd_create(args):
    desc = " ".join(args.description) if args.description else input("Describe your agent: ")
    result = _api("/api/agents/create", method="POST", data={"description": desc})
    if result.get("success"):
        print(f"\n  ✓ Created: {result.get('emoji','')} {result.get('name','')}")
        print(f"    Restart to load: agentos restart\n")
    else:
        print(f"\n  ✗ {result.get('error', 'Failed')}\n")


def cmd_doctor(args):
    """System health check."""
    plat = _get_platform()
    info = plat.get_system_info()

    print(f"\n  AgentOS Doctor")
    print(f"  {'─'*40}")
    print(f"  Platform:  {info['os']} {info['arch']}")
    print(f"  Python:    {info['python']}")

    # Check venv
    venv = plat.get_venv_python()
    print(f"  Venv:      {'✓' if venv.exists() else '✗'} {venv}")

    # Check config
    cfg = plat.get_config_dir() / "config.yaml"
    print(f"  Config:    {'✓' if cfg.exists() else '✗'} {cfg}")

    # Check data dir
    data = plat.get_data_dir()
    print(f"  Data dir:  {'✓' if data.exists() else '✗'} {data}")

    # Check port
    port = _get_port()
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("localhost", port))
        s.close()
        print(f"  Port {port}:  ✓ responding")
    except Exception:
        print(f"  Port {port}:  ✗ not responding")

    # Check daemon
    running = plat.is_service_running()
    print(f"  Daemon:    {'✓ running' if running else '✗ not running'}")
    print()


def main():
    parser = argparse.ArgumentParser(
        prog="agentos",
        description="AgentOS — The Agentic Operating System",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("install", help="Install as system daemon")
    sub.add_parser("uninstall", help="Remove system daemon")
    sub.add_parser("start", help="Start AgentOS")
    sub.add_parser("stop", help="Stop AgentOS")
    sub.add_parser("restart", help="Restart AgentOS")
    sub.add_parser("logs", help="Tail daemon logs")
    sub.add_parser("status", help="Show system status")
    sub.add_parser("list", help="List agents")
    sub.add_parser("doctor", help="System health check")

    create_p = sub.add_parser("create", help="Create agent from description")
    create_p.add_argument("description", nargs="*")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    cmds = {
        "install": cmd_install, "uninstall": cmd_uninstall,
        "start": cmd_start, "stop": cmd_stop, "restart": cmd_restart,
        "logs": cmd_logs, "status": cmd_status, "list": cmd_list,
        "create": cmd_create, "doctor": cmd_doctor,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
