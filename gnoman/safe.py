"""Safe orchestration layer for GNOMAN."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from eth_account import Account
from eth_account.signers.local import LocalAccount
from hexbytes import HexBytes
from web3 import Web3

from .abi import AbiManager
from .core import AppContext, get_context

HOLD_FILE = Path.home() / ".gnoman" / "safe_hold.json"
DELEGATE_FILE = Path.home() / ".gnoman" / "safe_delegates.json"
HOLD_SECONDS = 86_400
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


@dataclass
class SafeTransaction:
    to: str
    value: int
    data: bytes
    operation: int = 0
    safe_tx_gas: int = 0
    base_gas: int = 0
    gas_price: int = 0
    refund_receiver: str = ZERO_ADDRESS


class SafeManager:
    """High-level orchestration wrapper around a Gnosis Safe contract."""

    def __init__(self, context: Optional[AppContext] = None, *, safe_address: Optional[str] = None) -> None:
        self.context = context or get_context()
        self._abi = AbiManager(self.context)
        self._contract = None
        self._safe_address = safe_address
        self._hold_cache: Optional[Dict[str, Any]] = None

    # -- bootstrap --------------------------------------------------------
    def _load_contract(self) -> Any:
        if self._contract is not None:
            return self._contract
        payload = self._abi.safe_payload()
        address = self._safe_address or self.context.secrets.require(
            "GNOSIS_SAFE",
            prompt_text="Enter Safe address: ",
            sensitive=False,
        )
        checksum = Web3.to_checksum_address(address)
        web3 = self.context.get_web3()
        contract = web3.eth.contract(address=checksum, abi=payload.abi)
        self._contract = contract
        self._safe_address = checksum
        self.context.ledger.log(
            "safe_init",
            params={"safe": checksum},
            result={"abi_source": payload.source},
        )
        return contract

    @property
    def safe_address(self) -> str:
        self._load_contract()
        assert self._safe_address is not None
        return self._safe_address

    @property
    def contract(self):  # type: ignore[override]
        return self._load_contract()

    # -- hold -------------------------------------------------------------
    def _load_hold(self) -> Dict[str, Any]:
        if self._hold_cache is not None:
            return self._hold_cache
        if not HOLD_FILE.exists():
            self._hold_cache = {}
            return {}
        try:
            self._hold_cache = json.loads(HOLD_FILE.read_text(encoding="utf-8"))
        except Exception:
            self._hold_cache = {}
        return self._hold_cache

    def _write_hold(self, data: Dict[str, Any]) -> None:
        HOLD_FILE.parent.mkdir(parents=True, exist_ok=True)
        HOLD_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._hold_cache = data

    def _hold_key(self, nonce: int) -> str:
        return f"{self.safe_address}:{nonce}"

    def hold_entries(self) -> List[Dict[str, Any]]:
        now = int(time.time())
        entries = []
        for key, value in self._load_hold().items():
            entries.append({"key": key, "expires_at": int(value), "remaining": max(0, int(value) - now)})
        return entries

    def apply_hold(self, nonce: int) -> bool:
        key = self._hold_key(nonce)
        holds = self._load_hold()
        now = int(time.time())
        expires_at = int(holds.get(key, 0))
        if expires_at == 0:
            holds[key] = now + HOLD_SECONDS
            self._write_hold(holds)
            self.context.ledger.log(
                "safe_hold_place",
                params={"key": key},
                result={"until": holds[key]},
            )
            return False
        if now < expires_at:
            self.context.ledger.log(
                "safe_hold_block",
                params={"key": key},
                result={"remaining": expires_at - now},
            )
            return False
        holds.pop(key, None)
        self._write_hold(holds)
        self.context.ledger.log("safe_hold_release", params={"key": key})
        return True

    def release_hold(self, key: str) -> None:
        holds = self._load_hold()
        if key in holds:
            holds.pop(key)
            self._write_hold(holds)
            self.context.ledger.log("safe_hold_manual_release", params={"key": key})

    # -- delegates --------------------------------------------------------
    def _load_delegates(self) -> Dict[str, List[str]]:
        if not DELEGATE_FILE.exists():
            return {}
        try:
            return json.loads(DELEGATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_delegates(self, data: Dict[str, List[str]]) -> None:
        DELEGATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        DELEGATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def list_delegates(self) -> Dict[str, List[str]]:
        registry = self._load_delegates()
        self.context.ledger.log(
            "safe_delegate_list",
            params={"owners": len(registry)},
        )
        return registry

    def add_delegate(self, owner: str, delegate: str) -> Dict[str, Any]:
        registry = self._load_delegates()
        owner_cs = Web3.to_checksum_address(owner)
        delegate_cs = Web3.to_checksum_address(delegate)
        registry.setdefault(owner_cs, [])
        if delegate_cs not in registry[owner_cs]:
            registry[owner_cs].append(delegate_cs)
            self._write_delegates(registry)
            self.context.ledger.log(
                "safe_delegate_add",
                params={"owner": owner_cs, "delegate": delegate_cs},
            )
        return {"owner": owner_cs, "delegates": registry[owner_cs]}

    def remove_delegate(self, owner: str, delegate: str) -> Dict[str, Any]:
        registry = self._load_delegates()
        owner_cs = Web3.to_checksum_address(owner)
        delegate_cs = Web3.to_checksum_address(delegate)
        if owner_cs in registry and delegate_cs in registry[owner_cs]:
            registry[owner_cs].remove(delegate_cs)
            self._write_delegates(registry)
            self.context.ledger.log(
                "safe_delegate_remove",
                params={"owner": owner_cs, "delegate": delegate_cs},
            )
        return {"owner": owner_cs, "delegates": registry.get(owner_cs, [])}

    # -- safe state -------------------------------------------------------
    def owners(self) -> List[str]:
        owners = [Web3.to_checksum_address(o) for o in self.contract.functions.getOwners().call()]
        self.context.ledger.log("safe_owners", result={"count": len(owners)})
        return owners

    def threshold(self) -> int:
        threshold = int(self.contract.functions.getThreshold().call())
        self.context.ledger.log("safe_threshold", result={"threshold": threshold})
        return threshold

    def nonce(self) -> int:
        return int(self.contract.functions.nonce().call())

    def balance(self) -> Decimal:
        web3 = self.context.get_web3()
        wei = web3.eth.get_balance(self.safe_address)
        return Decimal(web3.from_wei(wei, "ether"))

    def guard(self) -> Optional[str]:
        try:
            guard_addr = self.contract.functions.getGuard().call()
            checksum = Web3.to_checksum_address(guard_addr)
            if int(guard_addr, 16) == 0:
                return None
            return checksum
        except Exception as exc:
            self.context.ledger.log(
                "safe_guard_error",
                ok=False,
                severity="ERROR",
                result={"error": str(exc)},
            )
            return None

    def info(self) -> Dict[str, Any]:
        owners = self.owners()
        threshold = self.threshold()
        nonce = self.nonce()
        balance = str(self.balance())
        guard = self.guard()
        hold = self.hold_entries()
        info = {
            "safe": self.safe_address,
            "owners": owners,
            "threshold": threshold,
            "nonce": nonce,
            "balance_eth": balance,
            "guard": guard,
            "hold": hold,
        }
        self.context.ledger.log("safe_info", result={"owners": len(owners), "threshold": threshold})
        return info

    # -- transaction helpers ---------------------------------------------
    def _signer(self, key: str) -> LocalAccount:
        secret = self.context.secrets.require(
            key,
            prompt_text=f"Enter private key for {key}: ",
            sensitive=True,
        )
        account = Account.from_key(secret)
        self.context.ledger.log(
            "safe_signer_load",
            params={"label": key},
            result={"address": Web3.to_checksum_address(account.address)},
        )
        return account

    def _prepare_transaction(self, tx: Dict[str, Any], signer: LocalAccount) -> Dict[str, Any]:
        web3 = self.context.get_web3()
        tx.setdefault("from", signer.address)
        tx.setdefault("chainId", getattr(web3.eth, "chain_id", 1))
        tx.setdefault("nonce", web3.eth.get_transaction_count(signer.address))
        if "gas" not in tx:
            try:
                estimate = web3.eth.estimate_gas({k: tx[k] for k in ("from", "to", "data", "value") if k in tx})
                tx["gas"] = int(estimate) + 100_000
            except Exception:
                tx["gas"] = 800_000
        if "maxFeePerGas" not in tx or "maxPriorityFeePerGas" not in tx:
            base = getattr(web3.eth, "gas_price", Web3.to_wei(2, "gwei"))
            tx["maxPriorityFeePerGas"] = Web3.to_wei(1, "gwei")
            tx["maxFeePerGas"] = max(base * 2, Web3.to_wei(3, "gwei"))
        return tx

    def _send_transaction(self, tx: Dict[str, Any], *, signer_key: str) -> Dict[str, Any]:
        signer = self._signer(signer_key)
        prepared = self._prepare_transaction(dict(tx), signer)
        web3 = self.context.get_web3()
        signed = signer.sign_transaction(prepared)
        tx_hash = web3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        ok = receipt.status == 1
        payload = {
            "hash": tx_hash.hex(),
            "block": receipt.blockNumber,
            "gas_used": receipt.gasUsed,
        }
        self.context.ledger.log(
            "safe_send_tx",
            params={"to": prepared.get("to"), "value": int(prepared.get("value", 0))},
            ok=ok,
            result=payload,
        )
        return payload

    # -- operations -------------------------------------------------------
    def fund_eth(self, amount_eth: Decimal, *, signer_key: str) -> Dict[str, Any]:
        value = int(Web3.to_wei(amount_eth, "ether"))
        nonce = self.nonce()
        if not self.apply_hold(nonce):
            raise RuntimeError("transaction placed on 24h hold; re-run after expiry")
        tx = {"to": self.safe_address, "value": value, "data": b""}
        result = self._send_transaction(tx, signer_key=signer_key)
        return {"tx": result}

    def send_erc20(self, token_address: str, amount: Decimal, *, signer_key: str) -> Dict[str, Any]:
        web3 = self.context.get_web3()
        token = web3.eth.contract(address=Web3.to_checksum_address(token_address), abi=[
            {"constant": False, "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
        ])
        decimals = token.functions.decimals().call()
        raw_amount = int(amount * (10 ** decimals))
        data = token.encodeABI(fn_name="transfer", args=[self.safe_address, raw_amount])
        tx = {"to": token.address, "value": 0, "data": HexBytes(data)}
        nonce = self.nonce()
        if not self.apply_hold(nonce):
            raise RuntimeError("transaction placed on 24h hold; re-run after expiry")
        result = self._send_transaction(tx, signer_key=signer_key)
        return {"tx": result}

    def add_owner(self, new_owner: str, *, signer_key: str) -> Dict[str, Any]:
        current_threshold = self.threshold()
        data = self.contract.encodeABI(
            fn_name="addOwnerWithThreshold",
            args=[Web3.to_checksum_address(new_owner), current_threshold],
        )
        return self._exec_safe_call(data, signer_key=signer_key)

    def remove_owner(self, owner: str, previous_owner: str, *, signer_key: str) -> Dict[str, Any]:
        threshold = self.threshold()
        data = self.contract.encodeABI(
            fn_name="removeOwner",
            args=[Web3.to_checksum_address(previous_owner), Web3.to_checksum_address(owner), threshold],
        )
        return self._exec_safe_call(data, signer_key=signer_key)

    def change_threshold(self, threshold: int, *, signer_key: str) -> Dict[str, Any]:
        if threshold <= 0:
            raise ValueError("threshold must be positive")
        data = self.contract.encodeABI(fn_name="changeThreshold", args=[threshold])
        return self._exec_safe_call(data, signer_key=signer_key)

    def set_guard(self, guard: str, *, signer_key: str) -> Dict[str, Any]:
        data = self.contract.encodeABI(fn_name="setGuard", args=[Web3.to_checksum_address(guard)])
        return self._exec_safe_call(data, signer_key=signer_key)

    def clear_guard(self, *, signer_key: str) -> Dict[str, Any]:
        data = self.contract.encodeABI(fn_name="setGuard", args=[Web3.to_checksum_address(ZERO_ADDRESS)])
        return self._exec_safe_call(data, signer_key=signer_key)

    def _exec_safe_call(self, data_hex: str, *, signer_key: str) -> Dict[str, Any]:
        nonce = self.nonce()
        if not self.apply_hold(nonce):
            raise RuntimeError("transaction placed on 24h hold; re-run after expiry")
        tx = {
            "to": self.safe_address,
            "value": 0,
            "data": HexBytes(data_hex),
        }
        result = self._send_transaction(tx, signer_key=signer_key)
        return {"tx": result}

    def build_safe_transaction(self, tx: SafeTransaction) -> Dict[str, Any]:
        nonce = self.nonce()
        tx_hash = self.contract.functions.getTransactionHash(
            Web3.to_checksum_address(tx.to),
            int(tx.value),
            tx.data,
            int(tx.operation),
            int(tx.safe_tx_gas),
            int(tx.base_gas),
            int(tx.gas_price),
            ZERO_ADDRESS,
            Web3.to_checksum_address(tx.refund_receiver),
            nonce,
        ).call()
        payload = {
            "safe": self.safe_address,
            "nonce": nonce,
            "hash": HexBytes(tx_hash).hex(),
        }
        self.context.ledger.log(
            "safe_tx_hash",
            params={"to": tx.to, "value": tx.value, "operation": tx.operation},
            result=payload,
        )
        return payload

    def exec_safe_transaction(
        self,
        tx: SafeTransaction,
        signatures: Sequence[str],
        *,
        signer_key: str,
    ) -> Dict[str, Any]:
        nonce = self.nonce()
        if not self.apply_hold(nonce):
            raise RuntimeError("transaction placed on 24h hold; re-run after expiry")
        sig_bytes = b"".join(self._normalise_signature(sig) for sig in signatures)
        call_data = self.contract.encodeABI(
            fn_name="execTransaction",
            args=[
                Web3.to_checksum_address(tx.to),
                int(tx.value),
                tx.data,
                int(tx.operation),
                int(tx.safe_tx_gas),
                int(tx.base_gas),
                int(tx.gas_price),
                ZERO_ADDRESS,
                Web3.to_checksum_address(tx.refund_receiver),
                sig_bytes,
            ],
        )
        tx_payload = {"to": self.safe_address, "value": 0, "data": HexBytes(call_data)}
        result = self._send_transaction(tx_payload, signer_key=signer_key)
        return {"tx": result}

    # -- helpers ----------------------------------------------------------
    def _normalise_signature(self, signature: str) -> bytes:
        sig = signature[2:] if signature.startswith("0x") else signature
        data = bytes.fromhex(sig)
        if len(data) != 65:
            raise ValueError("signature must be 65 bytes long")
        return data


def load_manager(context: Optional[AppContext] = None, *, safe_address: Optional[str] = None) -> SafeManager:
    return SafeManager(context=context, safe_address=safe_address)
