"""In-memory services that back the GNOMAN CLI."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

__all__ = [
    "AuditReporter",
    "AuditSigner",
    "RecoveryToolkit",
    "SafeVault",
    "SecretsStore",
    "get_audit_reporter",
    "get_audit_signer",
    "get_recovery_toolkit",
    "get_safe_vault",
    "get_secrets_store",
]


# --- Secrets management ----------------------------------------------------

_SECRETS_PRIORITY = ["keyring", "env", "env_secure", "hashicorp", "aws"]
_SECRETS_STORES: Dict[str, Dict[str, str]] = {
    "keyring": {
        "RPC_URL": "https://mainnet.infura.io/v3/demo",
        "SAFE_OWNER": "0xOwnerA",
        "DISCORD_WEBHOOK": "https://discord.example/webhook",
    },
    "env": {
        "RPC_URL": "https://mainnet.infura.io/v3/demo",
        "SAFE_OWNER": "0xOwnerB",
        "DISCORD_WEBHOOK": "https://discord.example/webhook",
    },
    "env_secure": {
        "RPC_URL": "https://mainnet.infura.io/v3/demo",
        "SAFE_OWNER": "0xOwnerA",
        "DISCORD_WEBHOOK": "https://discord.example/webhook",
    },
    "hashicorp": {
        "RPC_URL": "https://mainnet.infura.io/v3/demo",
        "SAFE_OWNER": "0xOwnerB",
        "DISCORD_WEBHOOK": "https://discord.example/webhook",
    },
    "aws": {
        "RPC_URL": "https://mainnet.infura.io/v3/demo",
        "SAFE_OWNER": "0xOwnerA",
        "DISCORD_WEBHOOK": "https://discord.example/webhook",
    },
}

_SECRETS_METADATA: Dict[str, Dict[str, Any]] = {
    "RPC_URL": {"expires_at": time.time() + 60 * 60 * 24 * 30, "last_access": time.time() - 600},
    "SAFE_OWNER": {"expires_at": time.time() + 60 * 60 * 24 * 2, "last_access": time.time() - 3600},
    "DISCORD_WEBHOOK": {"expires_at": time.time() + 60 * 60 * 24 * 7, "last_access": time.time() - 120},
}


class SecretsStore:
    """Coordinate reconciliation between the various secret stores."""

    def __init__(self, stores: Dict[str, Dict[str, str]], priority: Iterable[str]):
        self._stores = stores
        self._priority = list(priority)

    def snapshot(self) -> Dict[str, Dict[str, str]]:
        return {name: values.copy() for name, values in self._stores.items()}

    def keys(self) -> List[str]:
        keys: set[str] = set()
        for values in self._stores.values():
            keys.update(values.keys())
        return sorted(keys)

    def detect_drift(self, snapshot: Optional[Dict[str, Dict[str, str]]] = None) -> Dict[str, Dict[str, str]]:
        snap = snapshot or self.snapshot()
        drift: Dict[str, Dict[str, str]] = {}
        for key in self.keys():
            seen = {}
            for store, values in snap.items():
                if key in values:
                    seen[store] = values[key]
            if len(set(seen.values())) > 1:
                drift[key] = seen
        return drift

    def authoritative_value(self, key: str) -> Tuple[Optional[str], Optional[str]]:
        for store in self._priority:
            values = self._stores.get(store, {})
            if key in values:
                return store, values[key]
        return None, None

    def reconcile_priority(self) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []
        for key in self.keys():
            store, value = self.authoritative_value(key)
            if store is None:
                continue
            for target in self._stores.values():
                target[key] = value
            actions.append({"key": key, "value": value, "source": store, "mode": "priority"})
        return actions

    def apply_decisions(self, decisions: Dict[str, Tuple[str, str]]) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []
        for key, (store, value) in decisions.items():
            for target in self._stores.values():
                target[key] = value
            actions.append({"key": key, "value": value, "source": store, "mode": "manual"})
        return actions

    def force_sync(self) -> List[Dict[str, Any]]:
        return self.reconcile_priority()

    def set_secret(self, key: str, value: str) -> None:
        for store in self._stores.values():
            store[key] = value
        _SECRETS_METADATA[key] = {
            "expires_at": time.time() + 60 * 60 * 24 * 30,
            "last_access": time.time(),
        }

    def rotate_secret(self, key: str) -> str:
        new_value = hashlib.sha256(f"{key}-{time.time()}".encode("utf-8")).hexdigest()[:16]
        self.set_secret(key, new_value)
        return new_value

    def remove_secret(self, key: str) -> None:
        for store in self._stores.values():
            store.pop(key, None)
        _SECRETS_METADATA.pop(key, None)

    def metadata(self, key: str) -> Dict[str, Any]:
        return _SECRETS_METADATA.get(key, {})


# --- Safe state -------------------------------------------------------------

_WALLET_INVENTORY: List[Dict[str, Any]] = [
    {
        "name": "Executor-1",
        "address": "0xfeedfacecafebeef000000000000000000000001",
        "balance": 12.3,
        "last_access": time.time() - 1800,
    },
    {
        "name": "Executor-2",
        "address": "0xfeedfacecafebeef000000000000000000000002",
        "balance": 4.8,
        "last_access": time.time() - 4200,
    },
]

_SAFE_STATE: Dict[str, Dict[str, Any]] = {
    "0xSAFECORE": {
        "owners": ["0xOwnerA", "0xOwnerB", "0xOwnerC"],
        "threshold": 2,
        "proposals": [
            {
                "id": "1",
                "to": "0xabc",
                "value": "1 ETH",
                "status": "pending",
                "created_at": time.time() - 7200,
            },
            {
                "id": "2",
                "to": "0xdef",
                "value": "0.5 ETH",
                "status": "signed",
                "created_at": time.time() - 3600,
            },
        ],
    }
}

_ROTATION_STATE: Dict[str, Any] = {"last_rotation": None, "rotated_owners": []}
_FROZEN_ENTITIES: Dict[Tuple[str, str], Dict[str, Any]] = {}


def _timestamp() -> int:
    return int(time.time())


class AuditReporter:
    """Aggregate wallet, Safe, and secret metadata for forensic reports."""

    def collect(self) -> Dict[str, Any]:
        now = _timestamp()
        expiring: List[Dict[str, Any]] = []
        for key, meta in _SECRETS_METADATA.items():
            expires_at = int(meta.get("expires_at", 0))
            if expires_at and expires_at - now < 60 * 60 * 24 * 7:
                expiring.append(
                    {
                        "key": key,
                        "expires_at": expires_at,
                        "expires_in_days": round((expires_at - now) / (60 * 60 * 24), 2),
                    }
                )
        safes = []
        for address, data in _SAFE_STATE.items():
            safes.append(
                {
                    "address": address,
                    "owners": data["owners"],
                    "threshold": data["threshold"],
                    "queued": [
                        {
                            "id": proposal["id"],
                            "to": proposal["to"],
                            "value": proposal["value"],
                            "status": proposal["status"],
                        }
                        for proposal in data.get("proposals", [])
                    ],
                }
            )
        return {
            "generated_at": now,
            "wallets": _WALLET_INVENTORY,
            "safes": safes,
            "expiring_secrets": expiring,
        }


class AuditSigner:
    """Derive a deterministic signature using the GNOMAN audit key."""

    def __init__(self, key: str = "GNOMAN-AUDIT-KEY") -> None:
        self._key = key.encode("utf-8")

    def sign(self, payload: Dict[str, Any]) -> str:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(self._key + body).hexdigest()


class RecoveryToolkit:
    """Provide incident response helpers."""

    def start_safe_recovery(self, safe_address: str) -> Dict[str, Any]:
        safe = _SAFE_STATE.get(safe_address, _SAFE_STATE["0xSAFECORE"])
        steps = [
            "verify_owner_chain",
            "generate_replacement_signers",
            "stage_new_threshold_payload",
            "broadcast_emergency_rotation",
        ]
        return {
            "safe": safe_address,
            "current_threshold": safe["threshold"],
            "owners": safe["owners"],
            "steps": steps,
            "status": "wizard_started",
            "started_at": _timestamp(),
        }

    def rotate_all(self) -> Dict[str, Any]:
        new_owners = [f"0xROTATED{i:02d}" for i in range(1, 4)]
        _SAFE_STATE["0xSAFECORE"]["owners"] = new_owners
        _ROTATION_STATE["last_rotation"] = _timestamp()
        _ROTATION_STATE["rotated_owners"] = new_owners
        return {
            "timestamp": _ROTATION_STATE["last_rotation"],
            "owners": new_owners,
            "status": "rotated",
        }

    def freeze(self, target_type: str, target_id: str, reason: str) -> Dict[str, Any]:
        key = (target_type, target_id)
        entry = {
            "reason": reason,
            "frozen_at": _timestamp(),
            "unfreeze_token": hashlib.sha256(f"{target_type}:{target_id}:{time.time()}".encode()).hexdigest()[:12],
        }
        _FROZEN_ENTITIES[key] = entry
        return {"target_type": target_type, "target_id": target_id, **entry}


class SafeVault:
    """Track Safe proposals and state for CLI commands."""

    def __init__(self, state: Dict[str, Dict[str, Any]]):
        self._state = state
        self._counter = max(
            (int(p["id"]) for safe in state.values() for p in safe.get("proposals", [])),
            default=0,
        )

    def propose(self, to: str, value: str, data: str) -> Dict[str, Any]:
        self._counter += 1
        proposal = {
            "id": str(self._counter),
            "to": to,
            "value": value,
            "data": data,
            "status": "pending",
            "created_at": _timestamp(),
        }
        self._state.setdefault("0xSAFECORE", {}).setdefault("proposals", []).append(proposal)
        return proposal

    def sign(self, proposal_id: str) -> Dict[str, Any]:
        proposal = self._find(proposal_id)
        if proposal:
            proposal["status"] = "signed"
        return proposal or {"id": proposal_id, "status": "unknown"}

    def execute(self, proposal_id: str) -> Dict[str, Any]:
        proposal = self._find(proposal_id)
        if proposal:
            proposal["status"] = "executed"
        return proposal or {"id": proposal_id, "status": "unknown"}

    def status(self, safe_address: str) -> Dict[str, Any]:
        safe = self._state.get(safe_address)
        if not safe:
            return {"address": safe_address, "status": "unknown"}
        return {
            "address": safe_address,
            "owners": safe.get("owners", []),
            "threshold": safe.get("threshold"),
            "queued": safe.get("proposals", []),
        }

    def _find(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        for proposal in self._state.get("0xSAFECORE", {}).get("proposals", []):
            if proposal.get("id") == proposal_id:
                return proposal
        return None


_SECRETS_STORE = SecretsStore(_SECRETS_STORES, _SECRETS_PRIORITY)
_AUDIT_REPORTER = AuditReporter()
_AUDIT_SIGNER = AuditSigner()
_RECOVERY_TOOLKIT = RecoveryToolkit()
_SAFE_VAULT = SafeVault(_SAFE_STATE)


def get_secrets_store() -> SecretsStore:
    """Return the singleton secrets store."""

    return _SECRETS_STORE


def get_audit_reporter() -> AuditReporter:
    """Return the audit reporter singleton."""

    return _AUDIT_REPORTER


def get_audit_signer() -> AuditSigner:
    """Return the audit signer singleton."""

    return _AUDIT_SIGNER


def get_recovery_toolkit() -> RecoveryToolkit:
    """Return the recovery toolkit singleton."""

    return _RECOVERY_TOOLKIT


def get_safe_vault() -> SafeVault:
    """Return the Safe vault singleton."""

    return _SAFE_VAULT
