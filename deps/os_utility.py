"""
File containing several utility functions
"""

import psutil


def kill_process_by_name(name: str):
    """Kill all processes that match a given name."""
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if name in proc.info["name"] or any(name in c for c in proc.info["cmdline"]):
                print(f"Killing {name} PID={proc.info['pid']}")
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
