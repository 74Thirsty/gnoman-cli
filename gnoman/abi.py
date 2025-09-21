"""ABI orchestration helpers for GNOMAN."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .core import AppContext, get_context
from .utils.abi import load_safe_abi


@dataclass
class AbiPayload:
    """Container for the loaded Safe ABI payload and its origin."""

    abi: List[Dict[str, Any]]
    source: str


class AbiManager:
    """Manage ABI loading, validation, and encoding."""

    def __init__(self, context: Optional[AppContext] = None) -> None:
        self.context = context or get_context()
        self._safe_payload: Optional[AbiPayload] = None

    # -- loading ----------------------------------------------------------
    def safe_payload(self) -> AbiPayload:
        if self._safe_payload is None:
            abi, source = load_safe_abi()
            self._safe_payload = AbiPayload(abi=abi, source=source)
            self.context.ledger.log(
                "abi_load",
                params={"source": source},
                result={"entries": len(abi)},
            )
        return self._safe_payload

    # -- validation -------------------------------------------------------
    def validate_file(self, path: Path) -> Dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "abi" in payload:
            abi = payload["abi"]
        else:
            abi = payload
        if not isinstance(abi, list):
            raise ValueError("ABI payload must be an array")
        summary = {
            "functions": sum(1 for item in abi if item.get("type") == "function"),
            "events": sum(1 for item in abi if item.get("type") == "event"),
            "errors": sum(1 for item in abi if item.get("type") == "error"),
        }
        self.context.ledger.log(
            "abi_validate",
            params={"path": str(path)},
            result=summary,
        )
        return summary

    # -- encoding ---------------------------------------------------------
    def encode(self, function: str, args: Optional[List[Any]] = None, *, address: Optional[str] = None) -> Dict[str, Any]:
        payload = self.safe_payload()
        web3 = self.context.get_web3()
        contract = web3.eth.contract(address=address, abi=payload.abi)
        try:
            data = contract.encodeABI(fn_name=function, args=args or [])
        except ValueError as exc:
            self.context.ledger.log(
                "abi_encode",
                params={"function": function},
                ok=False,
                severity="ERROR",
                result={"error": str(exc)},
            )
            raise
        result = {"data": data, "function": function, "args": args or []}
        self.context.ledger.log(
            "abi_encode",
            params={"function": function},
            result={"length": len(data)},
        )
        return result

    def describe(self) -> Dict[str, Any]:
        payload = self.safe_payload()
        summary = self.validate_payload(payload.abi)
        summary["source"] = payload.source
        return summary

    # -- helpers ----------------------------------------------------------
    def validate_payload(self, abi: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "functions": sum(1 for item in abi if item.get("type") == "function"),
            "events": sum(1 for item in abi if item.get("type") == "event"),
            "errors": sum(1 for item in abi if item.get("type") == "error"),
        }


def load_manager(context: Optional[AppContext] = None) -> AbiManager:
    return AbiManager(context=context)
