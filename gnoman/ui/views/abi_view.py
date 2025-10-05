"""Interactive ABI testing surface for the GNOMAN dashboard."""


from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Static, TextLog
from web3 import Web3

from ...core import abi_manager


HISTORY_PATH = Path.home() / ".gnoman" / "history.json"


@dataclass
class _HistoryEntry:
    rpc: str
    contract: str
    method: str
    args: List[str]

    def to_payload(self) -> Dict[str, object]:
        return {"rpc": self.rpc, "contract": self.contract, "method": self.method, "args": self.args}

    @staticmethod
    def from_payload(payload: Dict[str, object]) -> "_HistoryEntry":
        rpc = str(payload.get("rpc", ""))
        contract = str(payload.get("contract", ""))
        method = str(payload.get("method", ""))
        args_raw = payload.get("args", [])
        args = [str(item) for item in args_raw] if isinstance(args_raw, list) else []
        return _HistoryEntry(rpc=rpc, contract=contract, method=method, args=args)


class ABIScreen(Vertical):
    """Interactive ABI testing surface."""

    BINDINGS = [
        ("enter", "trigger_call", "Simulate"),
        ("ctrl+enter", "trigger_send", "Send"),
    ]

    def __init__(self) -> None:
        super().__init__(id="abi")
        self.abi_table = DataTable(id="abi-list")
        self.method_table = DataTable(id="abi-methods")
        self.result_log = TextLog(id="abi-log", highlight=True, wrap=True)
        self.rpc_input = Input(placeholder="RPC URL", id="rpc-input")
        self.addr_input = Input(placeholder="Contract address", id="addr-input")
        self.args_input = Input(placeholder="Comma-separated arguments", id="args-input")
        self.call_btn = Button("Simulate Call", id="btn-call")
        self.send_btn = Button("Send TX", id="btn-send")
        self._methods: Dict[str, Dict[str, object]] = {}
        self._history: List[_HistoryEntry] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="abi-layout"):
            yield self.abi_table
            with Vertical(id="abi-details"):
                yield self.method_table
                yield Static("RPC Endpoint", classes="abi-label")
                yield self.rpc_input
                yield Static("Contract Address", classes="abi-label")
                yield self.addr_input
                yield Static("Arguments", classes="abi-label")
                yield self.args_input
                with Horizontal(id="abi-actions"):
                    yield self.call_btn
                    yield self.send_btn
                yield self.result_log

    async def on_mount(self) -> None:
        self._load_history()
        self.abi_table.add_columns("Available ABIs")
        for name in abi_manager.list_abis():
            self.abi_table.add_row(name, key=name)
        self.abi_table.cursor_type = "row"
        self.method_table.add_columns("Method", "Type", "State", "Inputs")
        self.method_table.cursor_type = "row"
        self.result_log.write("Select an ABI file to begin testing.")
        if self._history:
            last = self._history[-1]
            self.rpc_input.value = last.rpc
            self.addr_input.value = last.contract

    def action_trigger_call(self) -> None:
        self.call_btn.press()

    def action_trigger_send(self) -> None:
        self.send_btn.press()

    def _load_history(self) -> None:
        try:
            data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except json.JSONDecodeError:
            return
        entries = data if isinstance(data, list) else []
        for entry in entries:
            if isinstance(entry, dict):
                self._history.append(_HistoryEntry.from_payload(entry))

    def _save_history(self) -> None:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = [entry.to_payload() for entry in self._history[-10:]]
        HISTORY_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _record_history(self, rpc: str, contract: str, method: str, args: List[str]) -> None:
        self._history.append(_HistoryEntry(rpc=rpc, contract=contract, method=method, args=args))
        self._save_history()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:  # type: ignore[override]
        if event.data_table.id == "abi-list":
            self._handle_abi_selected(str(event.row_key))
        elif event.data_table.id == "abi-methods":
            self._handle_method_selected(str(event.row_key))

    def _handle_abi_selected(self, abi_name: str) -> None:
        try:
            abi_data = abi_manager.load_abi(abi_name)
        except Exception as exc:
            self.result_log.write(f"❌ Failed to load ABI: {exc}")
            return
        self._methods.clear()
        self.method_table.clear()
        for index, entry in enumerate(abi_data):
            if entry.get("type") != "function":
                continue
            inputs = entry.get("inputs", [])
            type_signature = ",".join(param.get("type", "") for param in inputs)
            signature = entry.get("name", "") or f"fn_{index}"
            if type_signature:
                signature = f"{signature}({type_signature})"
            input_desc = ", ".join(
                f"{param.get('name', '')}:{param.get('type', '')}".strip(":") for param in inputs
            )
            self.method_table.add_row(
                entry.get("name", "?"),
                entry.get("type", ""),
                entry.get("stateMutability", "-"),
                input_desc or "—",
                key=signature,
            )
            stored = dict(entry)
            stored["_signature"] = signature
            self._methods[signature] = stored
        if self.method_table.row_count:
            self.method_table.cursor_coordinate = (0, 0)
        self.result_log.write(f"Loaded ABI: {abi_name}")

    def _handle_method_selected(self, method: str) -> None:
        metadata = self._methods.get(method)
        if not metadata:
            return
        inputs = metadata.get("inputs", []) or []
        if inputs:
            placeholder = ", ".join(param.get("type", "") for param in inputs)
        else:
            placeholder = "No arguments"
        self.args_input.placeholder = placeholder
        self.args_input.value = self._history_lookup(method)
        self.result_log.write(f"Selected method: {metadata.get('name', method)}")

    def _history_lookup(self, method: str) -> str:
        for entry in reversed(self._history):
            if entry.method == method:
                return ", ".join(entry.args)
        return ""

    async def on_button_pressed(self, event: Button.Pressed) -> None:  # type: ignore[override]
        if event.button.id not in {"btn-call", "btn-send"}:
            return
        method_key = self.method_table.cursor_row_key
        abi_name = self.abi_table.cursor_row_key
        if not method_key or not abi_name:
            self.result_log.write("⚠️ Select both an ABI and a method before executing.")
            return
        metadata = self._methods.get(str(method_key))
        if not metadata:
            self.result_log.write("⚠️ Select a method first.")
            return
        method_name = str(metadata.get("name", method_key))
        rpc = self.rpc_input.value.strip()
        addr = self.addr_input.value.strip()
        if not rpc or not addr:
            self.result_log.write("⚠️ RPC URL and contract address are required.")
            return
        args = [item.strip() for item in self.args_input.value.split(",") if item.strip()]
        self.result_log.write(f"Connecting to {rpc}…")
        w3 = Web3(Web3.HTTPProvider(rpc))
        try:
            abi_data = abi_manager.load_abi(str(abi_name))
        except Exception as exc:
            self.result_log.write(f"❌ Unable to reload ABI: {exc}")
            return
        try:
            if event.button.id == "btn-call":
                result = await asyncio.to_thread(abi_manager.simulate_call, w3, addr, abi_data, method_name, args)
            else:
                private_key = os.getenv("GNOMAN_TEST_KEY")
                if not private_key:
                    self.result_log.write("⚠️ Set GNOMAN_TEST_KEY to send transactions.")
                    return
                result = await asyncio.to_thread(
                    abi_manager.send_transaction, w3, private_key, addr, abi_data, method_name, args
                )
        except Exception as exc:
            self.result_log.write(f"❌ Error: {exc}")
            return

        self._record_history(rpc, addr, str(method_key), args)
        try:
            formatted = json.dumps(result, indent=2, ensure_ascii=False)
        except TypeError:
            formatted = json.dumps(json.loads(Web3.to_json(result)), indent=2, ensure_ascii=False)  # type: ignore[arg-type]
        self.result_log.write(formatted)

=======
        self.send_btn = Button("Send Transaction", id="btn-send")

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield self.abi_table
            with Vertical():
                yield Static("Method List", classes="section-title")
                yield self.method_table
                yield Static("RPC Endpoint", classes="section-title")
                yield self.rpc_input
                yield Static("Contract Address", classes="section-title")
                yield self.addr_input
                yield Static("Arguments", classes="section-title")
                yield self.args_input
                yield Horizontal(self.call_btn, self.send_btn)
                yield Static("Execution Results", classes="section-title")
                yield self.result_log

    async def on_mount(self) -> None:
        self.abi_table.add_columns("Available ABIs")
        self.method_table.add_columns("Method", "Type", "State", "Inputs")
        self.result_log.write("🧩 ABI Tester ready. Select an ABI to begin.")
        await self.refresh_abi_list()

    async def refresh_abi_list(self) -> None:
        self.abi_table.clear()
        for name in abi_manager.list_abis():
            self.abi_table.add_row(name)
        self.abi_table.cursor_type = "row"

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Display methods when an ABI is selected."""
        if event.data_table.id != "abi-list":
            return
        abi_name = event.row_key
        abi_data = abi_manager.load_abi(abi_name)
        self.method_table.clear()
        for fn in abi_data:
            if fn.get("type") == "function":
                inputs = ", ".join(i.get("type", "?") for i in fn.get("inputs", []))
                self.method_table.add_row(
                    fn["name"],
                    fn["type"],
                    fn.get("stateMutability", "-"),
                    inputs,
                    key=fn["name"],
                )
        self.result_log.write(f"📜 Loaded ABI: {abi_name}")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        rpc = self.rpc_input.value.strip()
        address = self.addr_input.value.strip()
        args = [a.strip() for a in self.args_input.value.split(",") if a.strip()]
        abi_name = self.abi_table.cursor_row_key
        method = self.method_table.cursor_row_key

        if not abi_name:
            self.result_log.write("⚠️ Select an ABI first.")
            return
        if not method:
            self.result_log.write("⚠️ Select a method first.")
            return
        if not rpc or not address:
            self.result_log.write("⚠️ RPC endpoint and contract address are required.")
            return

        abi_data = abi_manager.load_abi(abi_name)
        w3 = Web3(Web3.HTTPProvider(rpc))

        try:
            if event.button.id == "btn-call":
                result = await asyncio.to_thread(
                    abi_manager.simulate_call, w3, address, abi_data, method, args
                )
                await asyncio.to_thread(append_record, "abi.simulate", result, True)
                self._display_result(result)
            elif event.button.id == "btn-send":
                pk = os.getenv("GNOMAN_TEST_KEY")
                if not pk:
                    self.result_log.write("⚠️ GNOMAN_TEST_KEY not set — cannot sign transaction.")
                    return
                result = await asyncio.to_thread(
                    abi_manager.send_transaction, w3, pk, address, abi_data, method, args
                )
                await asyncio.to_thread(append_record, "abi.execute", result, True)
                self._display_result(result)
        except Exception as exc:
            self.result_log.write(f"❌ Error: {exc}")

    def _display_result(self, result: Dict[str, Any]) -> None:
        try:
            formatted = json.dumps(result, indent=2)
        except Exception:
            formatted = str(result)
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        self.result_log.write(f"[{timestamp}] ✅ {formatted}")

