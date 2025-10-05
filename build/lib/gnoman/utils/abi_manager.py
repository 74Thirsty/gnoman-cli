# File: gnoman/utils/abi_manager.py
# Description: Dynamic ABI management + testing utilities for GNOMAN
# Author: Christopher Hirschauer

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from web3 import Web3
from eth_abi import encode_abi

ABI_CACHE_DIR = Path.home() / ".gnoman" / "abi_cache"
ABI_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class ABIManager:
    """Handles loading, storing, and testing contract ABIs."""

    def __init__(self, rpc_url: Optional[str] = None):
        self.rpc = rpc_url or os.getenv("GNOMAN_ETH_RPC")
        self.web3 = Web3(Web3.HTTPProvider(self.rpc)) if self.rpc else None

    def load(self, path: str) -> List[Dict[str, Any]]:
        """Load ABI from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("Invalid ABI format — must be a JSON array")
        return data

    def cache(self, name: str, abi: List[Dict[str, Any]]) -> Path:
        """Cache ABI under ~/.gnoman/abi_cache/<name>.json"""
        cache_path = ABI_CACHE_DIR / f"{name}.json"
        cache_path.write_text(json.dumps(abi, indent=2), encoding="utf-8")
        return cache_path

    def list_cached(self) -> List[str]:
        """List all cached ABIs by name."""
        return [f.stem for f in ABI_CACHE_DIR.glob("*.json")]

    def get_cached(self, name: str) -> Optional[List[Dict[str, Any]]]:
        """Retrieve cached ABI if it exists."""
        path = ABI_CACHE_DIR / f"{name}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def encode_function(self, abi: List[Dict[str, Any]], function: str, args: List[Any]) -> str:
        """Encode a function call using ABI."""
        for entry in abi:
            if entry.get("type") == "function" and entry.get("name") == function:
                types = [inp["type"] for inp in entry.get("inputs", [])]
                selector = self.web3.keccak(text=f"{function}({','.join(types)})")[:4]
                encoded_args = encode_abi(types, args)
                return "0x" + (selector + encoded_args).hex()
        raise ValueError(f"Function '{function}' not found in ABI")

    def test_call(self, contract_address: str, abi: List[Dict[str, Any]], function: str, args: List[Any]) -> Any:
        """Test call a function on-chain."""
        if not self.web3:
            raise RuntimeError("No RPC configured (set GNOMAN_ETH_RPC)")
        contract = self.web3.eth.contract(address=contract_address, abi=abi)
        fn = getattr(contract.functions, function)
        return fn(*args).call()


# CLI helper
def load_safe_abi(path: str) -> List[Dict[str, Any]]:
    """Compatibility wrapper for legacy code."""
    return ABIManager().load(path)
