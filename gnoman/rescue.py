"""Incident response and rotation utilities."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .core import AppContext, get_context
from .safe import SafeManager
from .sync import SecretSyncer
from .wallet import WalletService

FREEZE_REGISTRY = Path.home() / ".gnoman" / "freeze_registry.json"


def _ensure_file(path: Path, default: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(default, encoding="utf-8")


class RescueService:
    """Provide Safe rescue, rotation, and freeze workflows."""

    def __init__(self, context: Optional[AppContext] = None) -> None:
        self.context = context or get_context()
        self.wallet = WalletService(self.context)
        self.syncer = SecretSyncer(self.context)
        self._freeze_cache: Optional[Dict[str, Dict[str, Any]]] = None
        _ensure_file(FREEZE_REGISTRY, "{}")

    # -- helpers ----------------------------------------------------------
    def _load_freeze(self) -> Dict[str, Dict[str, Any]]:
        if self._freeze_cache is not None:
            return self._freeze_cache
        try:
            payload = json.loads(FREEZE_REGISTRY.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        self._freeze_cache = {str(key): dict(value) for key, value in payload.items() if isinstance(value, dict)}
        return self._freeze_cache

    def _write_freeze(self, data: Dict[str, Dict[str, Any]]) -> None:
        FREEZE_REGISTRY.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._freeze_cache = data

    # -- public API -------------------------------------------------------
    def rescue_safe(self, safe_address: Optional[str] = None) -> Dict[str, Any]:
        manager = SafeManager(self.context, safe_address=safe_address)
        info = manager.info()
        holds = manager.hold_entries()
        delegates = manager.list_delegates()
        drift = self.syncer.detect_drift()
        recommendations: List[str] = []
        if not info.get("guard"):
            recommendations.append("deploy delay guard")
        if holds:
            recommendations.append("review pending holds")
        if drift:
            recommendations.append("reconcile secrets drift")
        report = {
            "safe": info,
            "holds": holds,
            "delegates": delegates,
            "drift_keys": list(drift.keys()),
            "recommendations": recommendations,
        }
        self.context.ledger.log(
            "rescue_safe",
            params={"safe": info.get("address")},
            result={"holds": len(holds), "delegates": sum(len(v) for v in delegates.values())},
        )
        return report

    def rotate_all(self) -> Dict[str, Any]:
        manager = SafeManager(self.context)
        safe_info = manager.info()
        owners: List[str] = safe_info.get("owners", []) if isinstance(safe_info, dict) else []
        rotations: List[Dict[str, Any]] = []
        for index, owner in enumerate(owners, start=1):
            label = f"rotation-{index}"
            record = self.wallet.create_account(label, path="trading")
            rotations.append({"owner": owner, "label": label, "address": record["address"]})
        self.context.ledger.log(
            "rescue_rotate",
            params={"owners": len(owners)},
            result={"new_accounts": [entry["address"] for entry in rotations]},
        )
        return {"rotations": rotations, "owners": owners}

    def freeze(self, target_type: str, target_id: str, *, reason: str = "incident response") -> Dict[str, Any]:
        key = f"{target_type.lower()}::{target_id.lower()}"
        registry = self._load_freeze()
        record = {
            "target_type": target_type,
            "target_id": target_id,
            "reason": reason,
            "ts": time.time(),
        }
        registry[key] = record
        self._write_freeze(registry)
        self.context.ledger.log("rescue_freeze", params={"target": key, "reason": reason})
        return record

    def frozen(self) -> List[Dict[str, Any]]:
        return list(self._load_freeze().values())


def load_service(context: Optional[AppContext] = None) -> RescueService:
    return RescueService(context=context)
