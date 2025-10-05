"""ABI management and testing utilities for GNOMAN."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from eth_utils import to_checksum_address
from web3 import Web3
from web3.contract.contract import ContractFunction
from web3.exceptions import Web3Exception

from ..audit import append_record


ABI_DIRECTORY = Path.home() / ".gnoman" / "abis"


def _ensure_storage() -> None:
    ABI_DIRECTORY.mkdir(parents=True, exist_ok=True)


def _abi_path(name: str) -> Path:
    safe_name = name.strip()
    if not safe_name:
        raise ValueError("ABI name must be a non-empty string")
    if not safe_name.endswith(".json"):
        safe_name = f"{safe_name}.json"
    return (ABI_DIRECTORY / safe_name).resolve()


def list_abis() -> List[str]:
    """Return the known ABI entries sorted alphabetically."""

    _ensure_storage()
    entries = []
    for path in ABI_DIRECTORY.glob("*.json"):
        entries.append(path.stem)
    return sorted(entries)


def save_abi(name: str, abi_payload: Any) -> Path:
    """Persist an ABI payload to disk."""

    _ensure_storage()
    path = _abi_path(name)
    normalised = _normalise_payload(abi_payload)
    path.write_text(json.dumps(normalised, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _normalise_payload(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict) and "abi" in payload:
        abi_entries = payload.get("abi")
        metadata = dict(payload)
        metadata["abi"] = _normalise_abi(abi_entries)
        return metadata
    return {"abi": _normalise_abi(payload)}


def _normalise_abi(entries: Any) -> List[Dict[str, Any]]:
    if isinstance(entries, list):
        normalised: List[Dict[str, Any]] = []
        for entry in entries:
            if isinstance(entry, dict):
                normalised.append(dict(entry))
        if not normalised:
            raise ValueError("ABI definition is empty or invalid")
        return normalised
    raise ValueError("ABI definition must be a list of JSON objects")


def load_abi(name: str) -> List[Dict[str, Any]]:
    """Load an ABI definition from disk."""

    path = _abi_path(name)
    if not path.exists():
        raise FileNotFoundError(f"ABI '{name}' is not stored in {ABI_DIRECTORY}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _normalise_payload(payload)["abi"]


def load_abi_from_file(path: str | Path) -> List[Dict[str, Any]]:
    """Load an ABI definition directly from an arbitrary file path."""

    file_path = Path(path).expanduser()
    if not file_path.exists():
        raise FileNotFoundError(f"ABI file not found: {file_path}")
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    return _normalise_payload(payload)["abi"]


def _function_signature(abi_entries: Iterable[Dict[str, Any]], method: str) -> Dict[str, Any]:
    for entry in abi_entries:
        if entry.get("type") == "function" and entry.get("name") == method:
            return entry
    raise ValueError(f"Method '{method}' not found in ABI")


def _coerce_argument(value: str, abi_type: str) -> Any:
    if abi_type.endswith("[]"):
        inner_type = abi_type[:-2]
        try:
            parsed = json.loads(value or "[]")
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Array argument for {abi_type} must be valid JSON") from exc
        if not isinstance(parsed, list):
            raise ValueError(f"Array argument for {abi_type} must decode to a list")
        return [_coerce_argument(json.dumps(item) if isinstance(item, (list, dict)) else str(item), inner_type) for item in parsed]
    if abi_type.startswith("uint") or abi_type.startswith("int"):
        base = 10
        text = value.lower()
        if text.startswith("0x"):
            base = 16
        return int(value, base)
    if abi_type == "address":
        return to_checksum_address(value)
    if abi_type == "bool":
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        raise ValueError(f"Unable to parse boolean value '{value}'")
    if abi_type.startswith("bytes"):
        if value.startswith("0x"):
            return Web3.to_bytes(hexstr=value)
        return value.encode("utf-8")
    if abi_type == "string":
        return value
    if abi_type.startswith("tuple"):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ValueError("Tuple arguments must be provided as JSON arrays") from exc
        if not isinstance(parsed, list):
            raise ValueError("Tuple arguments must be represented as lists")
        return parsed
    return value


def _coerce_arguments(abi_entries: Sequence[Dict[str, Any]], method: str, args: Sequence[str]) -> List[Any]:
    signature = _function_signature(abi_entries, method)
    inputs = signature.get("inputs", [])
    if len(args) != len(inputs):
        raise ValueError(f"Method '{method}' expects {len(inputs)} arguments, received {len(args)}")
    coerced: List[Any] = []
    for raw, definition in zip(args, inputs):
        coerced.append(_coerce_argument(raw, str(definition.get("type", ""))))
    return coerced


def _serialise_result(result: Any) -> Any:
    try:
        return json.loads(Web3.to_json(result))
    except TypeError:
        if isinstance(result, (list, tuple)):
            return [_serialise_result(item) for item in result]
        if isinstance(result, bytes):
            return Web3.to_hex(result)
        return result


def _build_contract_function(
    w3: Web3, address: str, abi_data: Sequence[Dict[str, Any]], method: str, args: Sequence[str]
) -> ContractFunction:
    contract = w3.eth.contract(address=to_checksum_address(address), abi=abi_data)
    coerced_args = _coerce_arguments(abi_data, method, args)
    return getattr(contract.functions, method)(*coerced_args)


def simulate_call(w3: Web3, address: str, abi_data: Sequence[Dict[str, Any]], method: str, args: Sequence[str]) -> Dict[str, Any]:
    """Perform a non-state-changing call and return decoded results."""

    try:
        func = _build_contract_function(w3, address, abi_data, method, args)
        result = func.call()
        serialised = _serialise_result(result)
        payload = {"result": serialised, "timestamp": datetime.now(timezone.utc).isoformat()}
        _append_audit("abi.test", {"method": method, "contract": address, "mode": "call"}, True, payload)
        return payload
    except Exception as exc:
        _append_audit(
            "abi.test",
            {"method": method, "contract": address, "mode": "call"},
            False,
            {"error": str(exc)},
        )
        raise


def send_transaction(
    w3: Web3,
    private_key: str,
    address: str,
    abi_data: Sequence[Dict[str, Any]],
    method: str,
    args: Sequence[str],
) -> Dict[str, Any]:
    """Execute a write function, sign locally, and broadcast to the chain."""

    account = w3.eth.account.from_key(private_key)
    try:
        func = _build_contract_function(w3, address, abi_data, method, args)
        tx_params = {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
        }
        try:
            estimated_gas = func.estimate_gas(tx_params)
        except Web3Exception:
            estimated_gas = 2_000_000
        gas_price = w3.eth.gas_price
        tx: Dict[str, Any] = func.build_transaction({**tx_params, "gas": estimated_gas, "gasPrice": gas_price})
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        payload = {
            "tx_hash": tx_hash.hex(),
            "from": account.address,
            "gas": estimated_gas,
            "gas_price": gas_price,
        }
        _append_audit("abi.test", {"method": method, "contract": address, "mode": "send"}, True, payload)
        return payload
    except Exception as exc:
        _append_audit(
            "abi.test",
            {"method": method, "contract": address, "mode": "send"},
            False,
            {"error": str(exc)},
        )
        raise


def load_store(path: str | Path) -> Dict[str, Any]:
    """Load ABI selection metadata from ``path`` if it exists."""

    store_path = Path(path).expanduser()
    if not store_path.exists():
        return {}
    try:
        return json.loads(store_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def update_store(path: str | Path, last_path: str) -> Dict[str, Any]:
    """Persist the last used ABI path to ``path`` and return the payload."""

    store_path = Path(path).expanduser()
    store_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"last_path": str(last_path)}
    store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


__all__ = [
    "list_abis",
    "load_abi",
    "load_abi_from_file",
    "load_store",
    "save_abi",
    "send_transaction",
    "simulate_call",
    "update_store",
]

def _append_audit(action: str, params: Dict[str, Any], ok: bool, result: Dict[str, Any]) -> None:
    try:
        append_record(action, params, ok, result)
    except Exception:
        pass


