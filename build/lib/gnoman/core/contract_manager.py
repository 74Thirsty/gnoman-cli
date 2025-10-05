"""Smart contract tooling using Web3 + eth_abi."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from eth_abi import abi as eth_abi
from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider

from .log_manager import log_event


@dataclass
class ContractSummary:
    """Metadata describing a loaded contract."""

    name: str
    path: Path
    address: Optional[str]
    functions: List[Dict[str, object]]


class ContractManager:
    """Load ABIs and provide quick inspection helpers."""

    def __init__(self, *, rpc_url: Optional[str] = None) -> None:
        self._rpc_url = rpc_url or os.getenv("GNOMAN_ETH_RPC")
        self._web3: Optional[Web3] = None

    def _web3_client(self) -> Web3:
        if self._web3 is None:
            if self._rpc_url:
                self._web3 = Web3(Web3.HTTPProvider(self._rpc_url, request_kwargs={"timeout": 10}))
            else:
                self._web3 = Web3(EthereumTesterProvider())
        return self._web3

    @staticmethod
    def _normalise_abi(abi_definition: object) -> List[Dict[str, object]]:
        if isinstance(abi_definition, list):
            return [dict(entry) for entry in abi_definition if isinstance(entry, dict)]
        raise ValueError("Contract ABI must be a list of JSON objects")

    def _load_json(self, path: Path) -> dict:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "abi" in data:
            return data
        return {"abi": data, "contractName": path.stem}

    def load_contract(self, *, path: str, name: Optional[str] = None, address: Optional[str] = None) -> ContractSummary:
        json_path = Path(path).expanduser().resolve()
        payload = self._load_json(json_path)
        abi_definition = self._normalise_abi(payload["abi"])
        contract_name = name or str(payload.get("contractName", json_path.stem))
        client = self._web3_client()
        client.eth.contract(address=address, abi=abi_definition)  # Validate ABI
        summary = self._summarise_functions(contract_name, json_path, address, abi_definition)
        log_event("contract.load", path=str(json_path), name=contract_name, address=address)
        return summary

    def _summarise_functions(
        self,
        name: str,
        path: Path,
        address: Optional[str],
        abi_definition: List[Dict[str, object]],
    ) -> ContractSummary:
        functions: List[Dict[str, object]] = []
        for entry in abi_definition:
            if entry.get("type") != "function":
                continue
            inputs = entry.get("inputs", [])
            selector = self._selector(entry["name"], inputs)
            functions.append(
                {
                    "name": entry["name"],
                    "inputs": inputs,
                    "outputs": entry.get("outputs", []),
                    "stateMutability": entry.get("stateMutability", ""),
                    "selector": selector,
                }
            )
        return ContractSummary(name=name, path=path, address=address, functions=functions)

    @staticmethod
    def _selector(name: str, inputs: List[Dict[str, object]]) -> str:
        types = [str(param.get("type", "")) for param in inputs]
        placeholder_values: List[object] = []
        for typ in types:
            if typ.endswith("[]"):
                placeholder_values.append([])
            elif typ.startswith("uint") or typ.startswith("int"):
                placeholder_values.append(0)
            elif typ == "address":
                placeholder_values.append("0x" + "0" * 40)
            elif typ == "bool":
                placeholder_values.append(False)
            elif typ.startswith("bytes"):
                placeholder_values.append(b"")
            else:
                placeholder_values.append("")
        if types:
            eth_abi.encode_abi(types, placeholder_values)  # Validate parameter types
        signature = f"{name}({','.join(types)})"
        return Web3.keccak(text=signature)[:4].hex()


__all__ = ["ContractManager", "ContractSummary"]

