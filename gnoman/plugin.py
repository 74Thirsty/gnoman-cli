"""Plugin registry management for GNOMAN."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .core import AppContext, get_context

PLUGIN_REGISTRY_PATH = Path.home() / ".gnoman" / "plugins.json"


@dataclass
class PluginRecord:
    """Metadata describing an installed plugin."""

    name: str
    version: str
    schema: str
    enabled: bool = True
    installed_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())
    source: str = "manual"

    def serialise(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["installed_at"] = round(self.installed_at, 6)
        payload["updated_at"] = round(self.updated_at, 6)
        return payload


class PluginRegistry:
    """Persist plugin metadata with forensic logging."""

    def __init__(self, context: Optional[AppContext] = None, path: Path = PLUGIN_REGISTRY_PATH) -> None:
        self.context = context or get_context()
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")
        self._cache: Optional[Dict[str, PluginRecord]] = None

    # -- internal helpers -------------------------------------------------
    def _load(self) -> Dict[str, PluginRecord]:
        if self._cache is not None:
            return self._cache
        records: Dict[str, PluginRecord] = {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            payload = []
        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict) or "name" not in item:
                    continue
                record = PluginRecord(
                    name=str(item.get("name")),
                    version=str(item.get("version", "unknown")),
                    schema=str(item.get("schema", "unspecified")),
                    enabled=bool(item.get("enabled", True)),
                    installed_at=float(item.get("installed_at", time.time())),
                    updated_at=float(item.get("updated_at", time.time())),
                    source=str(item.get("source", "manual")),
                )
                records[record.name] = record
        self._cache = records
        return records

    def _write(self, records: Dict[str, PluginRecord]) -> None:
        payload = [record.serialise() for record in records.values()]
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._cache = records

    def _touch(self, record: PluginRecord) -> None:
        record.updated_at = time.time()

    # -- public API -------------------------------------------------------
    def list_plugins(self) -> List[Dict[str, object]]:
        records = self._load()
        data = [record.serialise() for record in records.values()]
        self.context.ledger.log("plugin_list", result={"count": len(data)})
        return data

    def add_plugin(self, name: str, version: str, schema: str, *, source: str = "manual") -> Dict[str, object]:
        records = self._load()
        now = time.time()
        record = PluginRecord(name=name, version=version, schema=schema, source=source, installed_at=now, updated_at=now)
        records[name] = record
        self._write(records)
        payload = record.serialise()
        self.context.ledger.log("plugin_add", params={"name": name, "version": version, "schema": schema, "source": source})
        return payload

    def remove_plugin(self, name: str) -> None:
        records = self._load()
        if name in records:
            records.pop(name)
            self._write(records)
            self.context.ledger.log("plugin_remove", params={"name": name})
        else:
            self.context.ledger.log("plugin_remove", params={"name": name}, ok=False, severity="WARNING")

    def swap(self, name: str, version: str) -> Dict[str, object]:
        records = self._load()
        if name not in records:
            raise KeyError(f"plugin {name} is not installed")
        record = records[name]
        record.version = version
        self._touch(record)
        self._write(records)
        payload = record.serialise()
        self.context.ledger.log("plugin_swap", params={"name": name, "version": version})
        return payload

    def toggle(self, name: str, *, enabled: bool) -> Dict[str, object]:
        records = self._load()
        if name not in records:
            raise KeyError(f"plugin {name} is not installed")
        record = records[name]
        record.enabled = enabled
        self._touch(record)
        self._write(records)
        payload = record.serialise()
        self.context.ledger.log("plugin_toggle", params={"name": name, "enabled": enabled})
        return payload

    def versions(self) -> Dict[str, str]:
        records = self._load()
        return {name: record.version for name, record in records.items()}


def load_registry(context: Optional[AppContext] = None) -> PluginRegistry:
    return PluginRegistry(context=context)
