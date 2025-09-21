"""Plugin management command handlers."""

from __future__ import annotations

from typing import Dict, List

from ..utils import aes, logbook


def _registry() -> aes.PluginRegistry:
    return aes.get_plugin_registry()


def list_plugins(args) -> Dict[str, List[Dict[str, object]]]:
    plugins = _registry().list()
    record = {
        "action": "plugin_list",
        "plugins": plugins,
        "status": "ok",
    }
    logbook.info(record)
    names = ", ".join(f"{entry['name']}@{entry['version']}" for entry in plugins)
    print(f"[PLUGIN] Installed plugins: {names}")
    return record


def add_plugin(args) -> Dict[str, object]:
    entry = _registry().add(args.name)
    record = {
        "action": "plugin_add",
        "plugin": entry,
        "status": "registered",
    }
    logbook.info(record)
    print(f"[PLUGIN] Added {entry['name']} ({entry['version']})")
    return record


def remove_plugin(args) -> Dict[str, object]:
    entry = _registry().remove(args.name)
    record = {
        "action": "plugin_remove",
        "plugin": entry,
    }
    logbook.info(record)
    status = "removed" if entry.get("removed") else "missing"
    print(f"[PLUGIN] {args.name} {status}.")
    return record


def swap(args) -> Dict[str, object]:
    try:
        entry = _registry().swap(args.name, args.version)
    except ValueError as exc:  # pragma: no cover - interactive error path
        record = {
            "action": "plugin_swap",
            "plugin": args.name,
            "status": "error",
            "error": str(exc),
        }
        logbook.info(record)
        print(f"[PLUGIN] Swap failed: {exc}")
        return record

    record = {
        "action": "plugin_swap",
        "plugin": entry,
        "status": "swapped",
    }
    logbook.info(record)
    print(
        "[PLUGIN] Swapped {name} {prev} → {version}".format(
            name=entry["name"], prev=entry["previous_version"], version=entry["version"]
        )
    )
    return record
