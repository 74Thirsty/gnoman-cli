"""Autopilot orchestration pipeline for GNOMAN."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .core import AppContext, get_context
from .plugin import PluginRegistry
from .safe import SafeManager, SafeTransaction
from .sync import SecretSyncer

AUTOPILOT_STATE_PATH = Path.home() / ".gnoman" / "autopilot_state.json"


@dataclass
class AutopilotReport:
    """Result of an autopilot run."""

    mode: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    plugin_versions: Dict[str, str] = field(default_factory=dict)
    transactions: List[Dict[str, Any]] = field(default_factory=list)
    plan_path: Optional[str] = None

    def serialise(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "steps": self.steps,
            "plugin_versions": self.plugin_versions,
            "transactions": self.transactions,
            "plan_path": self.plan_path,
        }


class AutopilotOrchestrator:
    """Coordinate sync, simulation, and execution of Safe plans."""

    def __init__(self, context: Optional[AppContext] = None) -> None:
        self.context = context or get_context()
        self.registry = PluginRegistry(self.context)
        self.safe = SafeManager(self.context)
        self.syncer = SecretSyncer(self.context)
        AUTOPILOT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # -- plan management --------------------------------------------------
    def load_plan(self, plan_path: Optional[Path]) -> Dict[str, Any]:
        if plan_path is None:
            return {
                "name": "default",
                "transactions": [],
                "alerts": ["drift", "balance"],
            }
        path = Path(plan_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("plan must be a JSON object")
        data.setdefault("transactions", [])
        data.setdefault("alerts", [])
        return data

    def _parse_transaction(self, payload: Dict[str, Any]) -> SafeTransaction:
        data_hex = str(payload.get("data", "0x"))
        if data_hex.startswith("0x"):
            data_hex = data_hex[2:]
        if len(data_hex) % 2:
            raise ValueError("transaction data must be even-length hex")
        data_bytes = bytes.fromhex(data_hex)
        return SafeTransaction(
            to=str(payload.get("to")),
            value=int(payload.get("value", 0)),
            data=data_bytes,
            operation=int(payload.get("operation", 0)),
            safe_tx_gas=int(payload.get("safe_tx_gas", 0)),
            base_gas=int(payload.get("base_gas", 0)),
            gas_price=int(payload.get("gas_price", 0)),
            refund_receiver=str(payload.get("refund", "0x0000000000000000000000000000000000000000")),
        )

    def _record_transactions(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        for index, payload in enumerate(transactions, start=1):
            try:
                tx = self._parse_transaction(payload)
                envelope = self.safe.build_safe_transaction(tx)
                records.append(
                    {
                        "index": index,
                        "to": envelope["to"],
                        "value": envelope["value"],
                        "operation": envelope["operation"],
                        "safeTxHash": envelope["safeTxHash"],
                    }
                )
            except Exception as exc:  # pragma: no cover - validation guard
                records.append({"index": index, "error": str(exc)})
        return records

    def _write_state(self, report: AutopilotReport) -> None:
        payload = {
            "ts": time.time(),
            **report.serialise(),
        }
        AUTOPILOT_STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # -- orchestration ----------------------------------------------------
    def execute(
        self,
        *,
        plan_path: Optional[Path] = None,
        dry_run: bool = False,
        execute: bool = False,
        alerts_only: bool = False,
    ) -> AutopilotReport:
        mode = "simulate"
        if alerts_only:
            mode = "alerts-only"
        elif execute:
            mode = "execute"
        elif dry_run:
            mode = "dry-run"

        plan = self.load_plan(plan_path)
        drift = self.syncer.detect_drift()
        steps: List[Dict[str, Any]] = [
            {"name": "secrets", "status": "drift" if drift else "ok", "details": {"keys": list(drift.keys())}},
        ]

        transactions = plan.get("transactions", [])
        transaction_records = self._record_transactions(transactions)
        if transaction_records:
            steps.append({"name": "plan", "status": "loaded", "details": {"count": len(transaction_records)}})
        else:
            steps.append({"name": "plan", "status": "empty"})

        executed: List[Dict[str, Any]] = []
        if execute and not alerts_only:
            for record, payload in zip(transaction_records, transactions):
                if "error" in record:
                    continue
                signatures = payload.get("signatures", [])
                try:
                    tx = self._parse_transaction(payload)
                    result = self.safe.exec_safe_transaction(tx, signatures, signer_key=payload.get("signer_key", "EXECUTOR"))
                    executed.append({"safeTxHash": result.get("safeTxHash"), "txHash": result.get("txHash")})
                except Exception as exc:  # pragma: no cover - execution guard
                    executed.append({"error": str(exc), "safeTxHash": record.get("safeTxHash")})
            steps.append({"name": "execution", "status": "complete", "details": {"count": len(executed)}})
        else:
            steps.append({"name": "execution", "status": "skipped", "details": {"mode": mode}})

        if alerts_only or drift:
            self.context.logger.warning("⚠️ Autopilot alerts: %s", list(drift.keys()))
            steps.append({"name": "alerts", "status": "dispatched", "details": {"alerts": list(drift.keys())}})
        else:
            steps.append({"name": "alerts", "status": "none"})

        report = AutopilotReport(
            mode=mode,
            steps=steps,
            plugin_versions=self.registry.versions(),
            transactions=transaction_records,
            plan_path=str(plan_path) if plan_path else None,
        )
        self.context.ledger.log(
            "autopilot_run",
            params={"mode": mode, "plan_path": str(plan_path) if plan_path else None},
            result={"steps": [step["name"] for step in steps], "transactions": len(transaction_records)},
        )
        self._write_state(report)
        return report


def load_orchestrator(context: Optional[AppContext] = None) -> AutopilotOrchestrator:
    return AutopilotOrchestrator(context=context)
