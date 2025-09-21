"""Autopilot orchestration command."""

from __future__ import annotations

from typing import Dict

from ..utils import aes, logbook


def run(args) -> Dict[str, object]:
    orchestrator = aes.get_autopilot()
    result = orchestrator.execute(
        plan_path=getattr(args, "plan", None),
        dry_run=bool(getattr(args, "dry_run", False)),
        execute=bool(getattr(args, "execute", False)),
        alerts_only=bool(getattr(args, "alerts_only", False)),
    )
    record = {
        "action": "autopilot",
        "mode": result["mode"],
        "steps": result["steps"],
        "plugin_versions": result["plugin_versions"],
    }
    logbook.info(record)
    for step in result["steps"]:
        print(f"[AUTOPILOT] {step['name']}: {step['status']}")
    print(f"[AUTOPILOT] Mode: {result['mode']}")
    return record
