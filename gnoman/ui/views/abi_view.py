"""Interactive ABI Testing Environment for GNOMAN."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, TextLog, Input, Button, Static
from textual import events
from web3 import Web3

from gnoman.core import abi_manager
from gnoman.audit import append_record


class ABIScreen(Vertical):
    """Interactive ABI testing and validation environment."""

    def __init__(self) -> None:
        super().__init__(id="abi-screen")
        self.abi_table = DataTable(id="abi-list")
        self.method_table = DataTable(id="method-list")
        self.result_log = TextLog(id="abi-log", highlight=True)
        self.rpc_input = Input(placeholder="RPC URL", id="rpc-input")
        self.addr_input = Input(placeholder="Contract address", id="addr-input")
        self.args_input = Input(placeholder="Comma-separated arguments", id="args-input")
        self.call_btn = Button("Simulate Call", id="btn-call")
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

