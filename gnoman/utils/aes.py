"""In-memory stand-ins for AES managers used by the GNOMAN CLI."""

from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SECRETS_PRIORITY = ["keyring", "env", "env_secure", "hashicorp", "aws"]
SECRETS_STORES: Dict[str, Dict[str, str]] = {
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

SECRETS_METADATA: Dict[str, Dict[str, Any]] = {
    "RPC_URL": {"expires_at": time.time() + 60 * 60 * 24 * 30, "last_access": time.time() - 600},
    "SAFE_OWNER": {"expires_at": time.time() + 60 * 60 * 24 * 2, "last_access": time.time() - 3600},
    "DISCORD_WEBHOOK": {"expires_at": time.time() + 60 * 60 * 24 * 7, "last_access": time.time() - 120},
}

WALLET_INVENTORY: List[Dict[str, Any]] = [
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

SAFE_STATE: Dict[str, Dict[str, Any]] = {
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

PLUGIN_REGISTRY: Dict[str, Dict[str, Any]] = {
    "balancer_trade": {"version": "v5.0", "schema": "trade-execution"},
    "ml-risk": {"version": "v1.3", "schema": "ml-score"},
}

PLUGIN_HISTORY: List[Dict[str, Any]] = []

FROZEN_ENTITIES: Dict[Tuple[str, str], Dict[str, Any]] = {}
ROTATION_STATE: Dict[str, Any] = {"last_rotation": None, "rotated_owners": []}

GRAPH_ROUTES: List[Dict[str, Any]] = [
    {
        "path": ["DAI", "ETH", "USDC"],
        "profit_bps": 24,
        "status": "active",
    },
    {
        "path": ["WBTC", "ETH", "ARB"],
        "profit_bps": -3,
        "status": "idle",
    },
]

ALERT_CHANNELS = ["Discord", "Slack", "PagerDuty"]


def _timestamp() -> int:
    return int(time.time())


class SecretsSyncCoordinator:
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
        SECRETS_METADATA[key] = {
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
        SECRETS_METADATA.pop(key, None)

    def metadata(self, key: str) -> Dict[str, Any]:
        return SECRETS_METADATA.get(key, {})


class AuditCollector:
    """Aggregate wallet, Safe, and secret metadata for forensic reports."""

    def collect(self) -> Dict[str, Any]:
        now = _timestamp()
        expiring: List[Dict[str, Any]] = []
        for key, meta in SECRETS_METADATA.items():
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
        for address, data in SAFE_STATE.items():
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
            "wallets": WALLET_INVENTORY,
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


class SimulationEngine:
    """Simulate transactions against a local fork."""

    def simulate(
        self,
        proposal_id: Optional[str],
        plan_path: Optional[str],
        trace: bool,
        ml_enabled: bool,
    ) -> Dict[str, Any]:
        plan_digest = ""
        plan_payload: Optional[Dict[str, Any]] = None
        if plan_path:
            path = Path(plan_path)
            if path.exists():
                try:
                    plan_payload = json.loads(path.read_text())
                except json.JSONDecodeError:
                    plan_payload = {"raw": path.read_text()}
        seed_source = plan_path or proposal_id or str(time.time())
        seed = int(hashlib.sha256(seed_source.encode("utf-8")).hexdigest(), 16)
        random.seed(seed)
        gas_used = random.randint(21000, 350000)
        success = random.random() > 0.1
        revert_reason = None if success else random.choice([
            "SAFE_THRESHOLD_NOT_MET",
            "ERC20: transfer amount exceeds balance",
            "AAVE: insufficient collateral",
        ])
        ml_score = None if not ml_enabled else round(random.uniform(0.6, 0.99), 3)
        plan_digest = hashlib.sha1(seed_source.encode("utf-8")).hexdigest()[:10]
        trace_steps: List[str] = []
        if trace:
            trace_steps = [
                "start_fork(anvil)",
                "deploy_safe_proxy()",
                f"execute_plan({plan_digest})",
                "collect_gas_metrics()",
            ]
        return {
            "proposal_id": proposal_id,
            "plan_path": plan_path,
            "plan_payload": plan_payload,
            "plan_digest": plan_digest,
            "success": success,
            "gas_used": gas_used,
            "revert_reason": revert_reason,
            "ml_score": ml_score,
            "trace": trace_steps,
        }


class RecoveryManager:
    """Provide incident response helpers."""

    def start_safe_recovery(self, safe_address: str) -> Dict[str, Any]:
        safe = SAFE_STATE.get(safe_address, SAFE_STATE["0xSAFECORE"])
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
        SAFE_STATE["0xSAFECORE"]["owners"] = new_owners
        ROTATION_STATE["last_rotation"] = _timestamp()
        ROTATION_STATE["rotated_owners"] = new_owners
        return {
            "timestamp": ROTATION_STATE["last_rotation"],
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
        FROZEN_ENTITIES[key] = entry
        return {"target_type": target_type, "target_id": target_id, **entry}


class GraphManager:
    """Render AES graph insights."""

    def render(self, fmt: str, output_path: Optional[str]) -> Dict[str, Any]:
        timestamp = _timestamp()
        root = Path.home() / ".gnoman" / "graphs"
        root.mkdir(parents=True, exist_ok=True)
        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path = root / f"graph-{timestamp}.{fmt}"
        highlight = [route for route in GRAPH_ROUTES if route["status"] == "active"]
        if fmt == "svg":
            neon_svg = self._render_svg(highlight)
            path.write_text(neon_svg, encoding="utf-8")
        elif fmt == "html":
            svg = self._render_svg(highlight)
            html = f"<html><body><h1>GNOMAN Graph</h1>{svg}</body></html>"
            path.write_text(html, encoding="utf-8")
        else:
            path.write_bytes(self._neon_png())
        return {
            "path": str(path),
            "format": fmt,
            "highlighted_routes": highlight,
            "generated_at": timestamp,
        }

    @staticmethod
    def _render_svg(routes: List[Dict[str, Any]]) -> str:
        lines = []
        for idx, route in enumerate(routes):
            y = 40 + idx * 40
            label = " → ".join(route["path"])
            lines.append(
                f'<text x="20" y="{y}" fill="#39FF14" font-family="monospace" font-size="18">{label} (bps {route["profit_bps"]})</text>'
            )
        content = "".join(lines) or "<text x=\"20\" y=\"40\" fill=\"#39FF14\">No active routes</text>"
        return f"<svg xmlns='http://www.w3.org/2000/svg' width='640' height='200' style='background:#050505'>{content}</svg>"

    @staticmethod
    def _neon_png() -> bytes:
        # 1x1 PNG with neon green pixel.
        return bytes(
            [
                0x89,
                0x50,
                0x4E,
                0x47,
                0x0D,
                0x0A,
                0x1A,
                0x0A,
                0x00,
                0x00,
                0x00,
                0x0D,
                0x49,
                0x48,
                0x44,
                0x52,
                0x00,
                0x00,
                0x00,
                0x01,
                0x00,
                0x00,
                0x00,
                0x01,
                0x08,
                0x02,
                0x00,
                0x00,
                0x00,
                0x90,
                0x77,
                0x53,
                0xDE,
                0x00,
                0x00,
                0x00,
                0x0A,
                0x49,
                0x44,
                0x41,
                0x54,
                0x08,
                0xD7,
                0x63,
                0xF8,
                0xCF,
                0xC0,
                0x00,
                0x00,
                0x03,
                0x00,
                0x01,
                0xE2,
                0x21,
                0xBC,
                0x33,
                0x00,
                0x00,
                0x00,
                0x00,
                0x49,
                0x45,
                0x4E,
                0x44,
                0xAE,
                0x42,
                0x60,
                0x82,
            ]
        )


class PluginRegistry:
    """Manage AES plugin metadata and enforce schema validation."""

    def list(self) -> List[Dict[str, Any]]:
        return [
            {"name": name, **info}
            for name, info in sorted(PLUGIN_REGISTRY.items())
        ]

    def add(self, name: str) -> Dict[str, Any]:
        entry = PLUGIN_REGISTRY.setdefault(name, {"version": "v1.0", "schema": "custom"})
        record = {"name": name, **entry, "status": "registered"}
        return record

    def remove(self, name: str) -> Dict[str, Any]:
        entry = PLUGIN_REGISTRY.pop(name, None)
        return {"name": name, "removed": entry is not None, "status": "removed"}

    def swap(self, name: str, version: str) -> Dict[str, Any]:
        if name not in PLUGIN_REGISTRY:
            raise ValueError(f"Unknown plugin: {name}")
        previous = PLUGIN_REGISTRY[name]["version"]
        schema = PLUGIN_REGISTRY[name]["schema"]
        if not schema:
            raise ValueError("Plugin schema missing; cannot validate swap")
        PLUGIN_REGISTRY[name]["version"] = version
        record = {
            "name": name,
            "previous_version": previous,
            "version": version,
            "schema": schema,
            "validated": True,
            "timestamp": _timestamp(),
        }
        PLUGIN_HISTORY.append(record)
        return record

    def snapshot_versions(self) -> Dict[str, str]:
        return {name: info["version"] for name, info in PLUGIN_REGISTRY.items()}

    def record_usage(self, plugin: str, version: str, context: str) -> None:
        PLUGIN_HISTORY.append(
            {
                "name": plugin,
                "version": version,
                "context": context,
                "timestamp": _timestamp(),
            }
        )


class Guardian:
    """Run monitoring cycles and emit alerts when thresholds drift."""

    def run(self, cycles: int) -> Dict[str, Any]:
        reports: List[Dict[str, Any]] = []
        alerts: List[str] = []
        for _ in range(max(1, cycles)):
            secrets_ok = not SecretsSyncCoordinator(SECRETS_STORES, SECRETS_PRIORITY).detect_drift()
            quorum_ok = SAFE_STATE["0xSAFECORE"]["threshold"] <= len(SAFE_STATE["0xSAFECORE"]["owners"])
            low_balances = [w for w in WALLET_INVENTORY if w["balance"] < 1]
            gas_price = random.randint(18, 64)
            profitable_routes = [r for r in GRAPH_ROUTES if r["profit_bps"] > 10]
            cycle = {
                "timestamp": _timestamp(),
                "secrets_ok": secrets_ok,
                "safe_quorum_ok": quorum_ok,
                "low_balances": [w["address"] for w in low_balances],
                "gas_gwei": gas_price,
                "profitable_routes": profitable_routes,
            }
            if not secrets_ok:
                alerts.append("Secret drift detected")
            if low_balances:
                alerts.append("Wallet balance below threshold")
            if profitable_routes:
                alerts.append("Arbitrage opportunity detected")
            reports.append(cycle)
        alert_targets = ALERT_CHANNELS if alerts else []
        return {
            "cycles": reports,
            "alerts": alerts,
            "alert_channels": alert_targets,
        }


class SafeRegistry:
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
        SAFE_STATE["0xSAFECORE"].setdefault("proposals", []).append(proposal)
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
        safe = SAFE_STATE.get(safe_address)
        if not safe:
            return {"address": safe_address, "status": "unknown"}
        return {
            "address": safe_address,
            "owners": safe["owners"],
            "threshold": safe["threshold"],
            "queued": safe.get("proposals", []),
        }

    def _find(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        for proposal in SAFE_STATE["0xSAFECORE"].get("proposals", []):
            if proposal["id"] == proposal_id:
                return proposal
        return None


class AutopilotOrchestrator:
    """Run the AES trade automation pipeline."""

    def __init__(self, plugin_registry: PluginRegistry, simulator: SimulationEngine) -> None:
        self._plugins = plugin_registry
        self._simulator = simulator

    def execute(
        self,
        plan_path: Optional[str],
        dry_run: bool,
        execute: bool,
        alerts_only: bool,
    ) -> Dict[str, Any]:
        plan_payload: Optional[Dict[str, Any]] = None
        if plan_path and Path(plan_path).exists():
            try:
                plan_payload = json.loads(Path(plan_path).read_text())
            except json.JSONDecodeError:
                plan_payload = {"raw": Path(plan_path).read_text()}
        steps: List[Dict[str, Any]] = []
        steps.append({"name": "fetch_loans", "status": "ok", "count": 3})
        steps.append({"name": "build_trades", "status": "ok", "paths": len(GRAPH_ROUTES)})
        ml_score = round(random.uniform(0.75, 0.98), 3)
        steps.append({"name": "ml_validate", "status": "ok", "score": ml_score})
        simulation = self._simulator.simulate(
            proposal_id="autopilot", plan_path=plan_path, trace=False, ml_enabled=True
        )
        steps.append({"name": "prepare_safe_payload", "status": "ok", "proposal": simulation["plan_digest"]})
        steps.append({"name": "simulate", "status": "ok", "gas_used": simulation["gas_used"]})
        mode = "alerts"
        if execute:
            mode = "execute"
        elif dry_run:
            mode = "dry-run"
        elif alerts_only:
            mode = "alerts"
        else:
            mode = "queue"
        steps.append({"name": "dispatch", "status": "ok", "mode": mode})
        plugin_versions = self._plugins.snapshot_versions()
        for name, version in plugin_versions.items():
            self._plugins.record_usage(name, version, context="autopilot")
        return {
            "mode": mode,
            "steps": steps,
            "plan_path": plan_path,
            "plan_payload": plan_payload,
            "plugin_versions": plugin_versions,
        }


_SECRETS_COORDINATOR = SecretsSyncCoordinator(SECRETS_STORES, SECRETS_PRIORITY)
_AUDIT_COLLECTOR = AuditCollector()
_AUDIT_SIGNER = AuditSigner()
_SIMULATION_ENGINE = SimulationEngine()
_RECOVERY_MANAGER = RecoveryManager()
_GRAPH_MANAGER = GraphManager()
_PLUGIN_REGISTRY = PluginRegistry()
_GUARDIAN = Guardian()
_SAFE_REGISTRY = SafeRegistry(SAFE_STATE)
_AUTOPILOT = AutopilotOrchestrator(_PLUGIN_REGISTRY, _SIMULATION_ENGINE)


def get_secrets_coordinator() -> SecretsSyncCoordinator:
    return _SECRETS_COORDINATOR


def get_audit_collector() -> AuditCollector:
    return _AUDIT_COLLECTOR


def get_audit_signer() -> AuditSigner:
    return _AUDIT_SIGNER


def get_simulation_engine() -> SimulationEngine:
    return _SIMULATION_ENGINE


def get_recovery_manager() -> RecoveryManager:
    return _RECOVERY_MANAGER


def get_graph_manager() -> GraphManager:
    return _GRAPH_MANAGER


def get_plugin_registry() -> PluginRegistry:
    return _PLUGIN_REGISTRY


def get_guardian() -> Guardian:
    return _GUARDIAN


def get_safe_registry() -> SafeRegistry:
    return _SAFE_REGISTRY


def get_autopilot() -> AutopilotOrchestrator:
    return _AUTOPILOT
