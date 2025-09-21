"""Transaction simulation and execution helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .autopilot import AutopilotOrchestrator
from .core import AppContext, get_context

PLANS_DIR = Path.home() / ".gnoman" / "plans"


class TransactionService:
    """Bridge between CLI transaction commands and the autopilot engine."""

    def __init__(self, context: Optional[AppContext] = None) -> None:
        self.context = context or get_context()
        self.orchestrator = AutopilotOrchestrator(self.context)
        PLANS_DIR.mkdir(parents=True, exist_ok=True)

    def _resolve_plan(self, proposal_id: Optional[str], plan_path: Optional[Path]) -> Optional[Path]:
        if plan_path is not None:
            return Path(plan_path)
        if proposal_id:
            candidate = PLANS_DIR / f"{proposal_id}.json"
            if candidate.exists():
                return candidate
        return None

    def simulate(
        self,
        proposal_id: Optional[str] = None,
        *,
        plan_path: Optional[Path] = None,
        trace: bool = False,
        ml_off: bool = False,
    ) -> Dict[str, Any]:
        plan = self._resolve_plan(proposal_id, plan_path)
        report = self.orchestrator.execute(plan_path=plan, dry_run=True)
        payload = report.serialise()
        payload.update({"proposal_id": proposal_id, "trace": trace, "ml_off": ml_off})
        self.context.ledger.log(
            "tx_simulate",
            params={"proposal_id": proposal_id, "trace": trace, "ml_off": ml_off},
            result={"transactions": len(payload.get("transactions", []))},
        )
        return payload

    def execute(self, proposal_id: str, *, plan_path: Optional[Path] = None) -> Dict[str, Any]:
        plan = self._resolve_plan(proposal_id, plan_path)
        report = self.orchestrator.execute(plan_path=plan, execute=True)
        payload = report.serialise()
        payload.update({"proposal_id": proposal_id})
        self.context.ledger.log(
            "tx_execute",
            params={"proposal_id": proposal_id},
            result={"transactions": len(payload.get("transactions", []))},
        )
        return payload


def load_service(context: Optional[AppContext] = None) -> TransactionService:
    return TransactionService(context=context)
