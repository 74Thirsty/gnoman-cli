"""Plugin management command stubs."""

from __future__ import annotations

from typing import Dict, List

from ..utils import logbook


def list_plugins(args) -> Dict[str, List[str]]:
    plugins = ["defi-router", "ml-risk"]
    record = {
        "action": "plugin_list",
        "plugins": plugins,
        "status": "stub",
    }
    logbook.info(record)
    print(f"[PLUGIN] Installed plugins: {', '.join(plugins)}")
    return record


def add_plugin(args) -> Dict[str, str]:
    record = {
        "action": "plugin_add",
        "name": args.name,
        "status": "stub",
    }
    logbook.info(record)
    print(f"[PLUGIN] Added {args.name}")
    return record


def remove_plugin(args) -> Dict[str, str]:
    record = {
        "action": "plugin_remove",
        "name": args.name,
        "status": "stub",
    }
    logbook.info(record)
    print(f"[PLUGIN] Removed {args.name}")
    return record
