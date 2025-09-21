"""Graph visualisation command handlers."""

from __future__ import annotations

from typing import Dict

from ..utils import aes, logbook


def view(args) -> Dict[str, object]:
    manager = aes.get_graph_manager()
    result = manager.render(args.format, getattr(args, "output", None))
    record = {
        "action": "graph_view",
        "format": result["format"],
        "path": result["path"],
        "highlighted": result["highlighted_routes"],
    }
    logbook.info(record)
    print(f"[GRAPH] Rendered {result['format']} graph → {result['path']}")
    return record
