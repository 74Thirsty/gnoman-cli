"""Interactive Textual dashboard for the GNOMAN control console."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import textwrap
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import lru_cache
from typing import Dict, List, Optional, Sequence

from rich.pretty import Pretty
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, ContentSwitcher, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, DataTable, Footer, Static

from web3 import Web3
from web3.exceptions import Web3Exception

from . import __version__
from .audit import append_record, read_tail_records, verify_tail
from .utils import keyring_backend


RPC_ENVIRONMENT_VARIABLE = "GNOMAN_ETH_RPC"
ANIMATION_TIMING = 0.12


@dataclass(slots=True)
class NetworkMetrics:
    network_label: str
    block_height: str
    gas_price: str
    latency_ms: str
    timestamp: datetime


class NavigationBar(Container):
    """Primary navigation row with tab buttons."""

    class TabSelected(Message):
        def __init__(self, tab: str) -> None:
            super().__init__()
            self.tab = tab

    def __init__(self) -> None:
        super().__init__(id="nav")
        self._buttons: Dict[str, Button] = {}

    def compose(self) -> ComposeResult:
        tabs = [
            ("overview", "Overview"),
            ("secrets", "Secrets"),
            ("wallets", "Wallets"),
            ("safes", "Safes"),
            ("contracts", "Contracts"),
            ("audit", "Audit"),
            ("sync", "Sync"),
        ]
        with Horizontal(id="nav-buttons"):
            for tab_id, label in tabs:
                button = Button(label, id=f"tab-{tab_id}", classes="nav-button", name=tab_id)
                self._buttons[tab_id] = button
                yield button

    def set_active(self, tab: str) -> None:
        for tab_id, button in self._buttons.items():
            if tab_id == tab:
                button.add_class("active")
            else:
                button.remove_class("active")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.name:
            self.post_message(self.TabSelected(event.button.name))


class HeaderBar(Container):
    """Top level telemetry bar."""

    def __init__(self) -> None:
        super().__init__(id="header")
        self._network = Static("Network: —", id="hdr-network", classes="header-cell")
        self._block = Static("Block: —", id="hdr-block", classes="header-cell")
        self._gas = Static("Gas: —", id="hdr-gas", classes="header-cell")
        self._drift = Static("Drift: —", id="hdr-drift", classes="header-cell")
        self._timestamp = Static("", id="hdr-timestamp", classes="header-cell")

    def compose(self) -> ComposeResult:
        with Horizontal(id="header-row"):
            yield self._network
            yield self._block
            yield self._gas
            yield self._drift
            yield self._timestamp

    async def update_metrics(self) -> None:
        try:
            metrics = await asyncio.to_thread(fetch_network_metrics)
        except NotImplementedError as exc:
            self._network.update(f"Network: {exc}")
            self._block.update("Block: —")
            self._gas.update("Gas: —")
            self._timestamp.update("RPC not configured")
        except Exception as exc:  # pragma: no cover - depends on external RPC
            self._network.update(f"Network error: {exc}")
            self._block.update("Block: —")
            self._gas.update("Gas: —")
            self._timestamp.update("RPC failure")
        else:
            self._network.update(f"Network: {metrics.network_label}")
            self._block.update(f"Block: {metrics.block_height}")
            self._gas.update(f"Gas: {metrics.gas_price}")
            self._timestamp.update(metrics.timestamp.astimezone(timezone.utc).strftime("%H:%M:%S UTC"))

        try:
            summary = await asyncio.to_thread(keyring_backend.audit_entries, stale_days=180)
        except Exception as exc:
            self._drift.update(f"Drift: audit unavailable ({exc})")
        else:
            stale = len(summary.get("stale", []))
            duplicates = len(summary.get("duplicates", []))
            drift_summary = f"Drift: {stale} stale / {duplicates} duplicate"
            if stale or duplicates:
                self._drift.update(Text(drift_summary, style="#FF6600"))
            else:
                self._drift.update(Text("Drift: nominal", style="#39FF14"))


class OverviewScreen(Container):
    """Overview screen with telemetry tiles and audit tail."""

    def __init__(self) -> None:
        super().__init__(id="overview")
        self._wallet_tile = Static("Wallets\nConfigure GNOMAN wallet integration", classes="tile")
        self._safe_tile = Static("Safes\nConnect safe-eth-py integration", classes="tile")
        self._drift_tile = Static("Keyring Drift\n—", classes="tile")
        self._audit_tile = Static("Last Audit\nNo audit recorded", classes="tile")
        self._telemetry_panel = Static("", classes="panel")
        self._log_panel = Static("", classes="panel log")

    def compose(self) -> ComposeResult:
        with Vertical(id="overview-container"):
            with Horizontal(id="overview-tiles"):
                yield self._wallet_tile
                yield self._safe_tile
                yield self._drift_tile
                yield self._audit_tile
            yield Static("Telemetry", classes="section-title")
            yield self._telemetry_panel
            yield Static("Forensic Log Tail", classes="section-title")
            yield self._log_panel

    async def on_mount(self) -> None:
        await self.refresh()
        self.set_interval(15.0, self.refresh)

    async def refresh(self) -> None:
        try:
            summary = await asyncio.to_thread(keyring_backend.audit_entries, stale_days=180)
        except Exception as exc:
            self._drift_tile.update(f"Keyring Drift\nAudit unavailable: {exc}")
        else:
            stale = len(summary.get("stale", []))
            duplicates = len(summary.get("duplicates", []))
            drift = f"{stale} stale / {duplicates} duplicates"
            style = "[#39FF14]Nominal[/]" if not stale and not duplicates else f"[#FF6600]{drift}[/]"
            self._drift_tile.update(f"Keyring Drift\n{style}")

        tail_records = await asyncio.to_thread(read_tail_records, 8)
        if tail_records:
            lines = []
            for record in tail_records:
                timestamp = record.get("timestamp")
                ts_text = "unknown"
                if isinstance(timestamp, (int, float)):
                    ts_text = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                lines.append(f"{ts_text} — {record.get('action')} → {record.get('result')}")
            self._log_panel.update("\n".join(lines))
            if len(tail_records) >= 1:
                last_audit = next((r for r in reversed(tail_records) if r.get("action") == "audit.run"), None)
                if last_audit:
                    ts = last_audit.get("timestamp")
                    if isinstance(ts, (int, float)):
                        human = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                        self._audit_tile.update(f"Last Audit\n{human}")
        else:
            self._log_panel.update("Audit log empty. Configure GNOMAN-AUDIT-KEY to enable signing.")

        try:
            metrics = await asyncio.to_thread(fetch_network_metrics)
        except NotImplementedError as exc:
            self._telemetry_panel.update(str(exc))
        except Exception as exc:  # pragma: no cover - external RPC
            self._telemetry_panel.update(f"RPC error: {exc}")
        else:
            detail = (
                f"Network: {metrics.network_label}\n"
                f"Block Height: {metrics.block_height}\n"
                f"Gas Price: {metrics.gas_price}\n"
                f"Latency: {metrics.latency_ms}\n"
                f"Updated: {metrics.timestamp.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
            self._telemetry_panel.update(detail)


class SecretsScreen(Container):
    """Secrets management surface backed by the OS keyring."""

    def __init__(self) -> None:
        super().__init__(id="secrets")
        self._table = DataTable(id="secrets-table")
        self._inspector = Static("Select an entry", id="secrets-inspector", classes="panel")
        self._metadata: Dict[str, Dict[str, object]] = {}

    def compose(self) -> ComposeResult:
        with Horizontal(id="secrets-layout"):
            yield self._table
            yield self._inspector

    async def on_mount(self) -> None:
        self._table.add_columns("Service", "Username", "Modified", "Status")
        self._table.zebra_stripes = True
        self._table.cursor_type = "row"
        await self.refresh()
        self.set_interval(30.0, self.refresh)

    async def refresh(self) -> None:
        try:
            entries = await asyncio.to_thread(keyring_backend.list_all_entries)
        except Exception as exc:
            self._table.clear()
            self._inspector.update(f"Keyring unavailable: {exc}")
            return
        self._table.clear()
        self._metadata.clear()
        threshold = datetime.now(timezone.utc) - timedelta(days=90)
        for entry in entries:
            metadata = entry.metadata if isinstance(entry.metadata, dict) else {}
            modified = metadata.get("modified")
            modified_text = "—"
            modified_dt: Optional[datetime] = None
            if isinstance(modified, datetime):
                modified_dt = modified if modified.tzinfo else modified.replace(tzinfo=timezone.utc)
            elif isinstance(modified, str):
                try:
                    modified_dt = datetime.fromisoformat(modified)
                    if modified_dt.tzinfo is None:
                        modified_dt = modified_dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    modified_dt = None
            if modified_dt:
                modified_text = modified_dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
            stale = bool(modified_dt and modified_dt < threshold)
            status = "Nominal"
            if stale:
                status = "Stale"
            elif not entry.username:
                status = "Missing username"
            row_key = f"{entry.service}:{entry.username}:{len(self._metadata)}"
            self._metadata[row_key] = metadata
            status_render = Text(status)
            if status == "Stale":
                status_render = Text("Stale", style="#FF6600")
            elif status == "Nominal":
                status_render = Text("Nominal", style="#39FF14")
            elif status == "Missing username":
                status_render = Text("Missing username", style="#FF6600")
            self._table.add_row(
                entry.service or "—",
                entry.username or "—",
                modified_text,
                status_render,
                key=row_key,
            )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        metadata = self._metadata.get(event.row_key, {})
        if metadata:
            self._inspector.update(Pretty(metadata, expand_all=True))
        else:
            self._inspector.update("No metadata available for this entry")


class PendingIntegration(Static):
    """Widget displayed for integrations that are not yet implemented."""

    def __init__(self, message: str, *, tab_id: str) -> None:
        super().__init__(message, id=tab_id, classes="pending")


class MainPanel(Container):
    """Content switcher managing the active tab."""

    def __init__(self) -> None:
        super().__init__(id="main")
        self._switcher = ContentSwitcher(initial="overview", id="main-switcher")

    def compose(self) -> ComposeResult:
        with self._switcher:
            yield OverviewScreen()
            yield SecretsScreen()
            yield PendingIntegration(
                "Wallet orchestration requires hardware-signing integration. Configure Web3 + ledger to enable.",
                tab_id="wallets",
            )
            yield PendingIntegration(
                "Safe management depends on safe-eth-py configuration. Connect to a Safe service to continue.",
                tab_id="safes",
            )
            yield PendingIntegration(
                "Contract cockpit requires ABI indexing via web3 + eth_abi. Provide contract metadata to activate.",
                tab_id="contracts",
            )
            yield PendingIntegration(
                "Run audits from automation mode or connect audit pipeline to view results here.",
                tab_id="audit",
            )
            yield PendingIntegration(
                "Sync console reconciles keyring↔env once sync adapters are configured.",
                tab_id="sync",
            )

    def show_tab(self, tab: str) -> None:
        self._switcher.current = tab


class FooterBar(Container):
    """Footer containing audit log tail information."""

    def __init__(self) -> None:
        super().__init__(id="footer")
        self._log_tail = Static("", id="footer-log")

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield self._log_tail
        yield Footer()

    async def on_mount(self) -> None:
        await self.refresh()
        self.set_interval(10.0, self.refresh)

    async def refresh(self) -> None:
        records = await asyncio.to_thread(read_tail_records, 3)
        if not records:
            self._log_tail.update("Audit log empty. Use GNOMAN-AUDIT-KEY to enable signed records.")
            return
        try:
            verified = await asyncio.to_thread(verify_tail, records)
        except Exception:
            verified = False
        status = "[#39FF14]verified[/]" if verified else "[#FF6600]unverified[/]"
        formatted = [
            textwrap.shorten(json.dumps(record, ensure_ascii=False), width=160, placeholder="…")
            for record in records
        ]
        self._log_tail.update(Text(" | ".join(formatted) + f" ({status})"))


class NeonControlApp(App[None]):
    """Textual application implementing the GNOMAN dashboard."""

    CSS = """
    Screen {
        background: #000A0F;
        color: #E0E0E0;
    }

    #header {
        background: #00121A;
        padding: 1 2;
        border-bottom: solid #00B7FF;
    }

    #header-row {
        layout: horizontal;
        gap: 2;
    }

    .header-cell {
        text-style: bold;
    }

    #nav {
        padding: 0 2;
        border-bottom: solid #00B7FF;
    }

    #nav-buttons {
        gap: 1;
    }

    Button.nav-button {
        background: #001B29;
        color: #E0E0E0;
        border: tall transparent;
        padding: 0 2;
        transition: background {animation}s ease-in-out;
    }

    Button.nav-button:hover {
        background: #00324F;
    }

    Button.nav-button.active {
        background: #00B7FF;
        color: #000A0F;
    }

    #main {
        padding: 1 2;
    }

    #overview-tiles {
        gap: 2;
    }

    .tile {
        background: #00121A;
        padding: 1 2;
        border: rounded #00B7FF;
        min-width: 24;
        transition: offset {animation}s ease-in-out;
    }

    .panel {
        background: #00121A;
        padding: 1 2;
        border: round #00324F;
    }

    .panel.log {
        height: 6;
        overflow-y: auto;
    }

    .section-title {
        color: #00B7FF;
        text-style: bold;
        padding-top: 1;
    }

    #secrets-layout {
        height: 1fr;
        gap: 2;
    }

    #secrets-table {
        width: 2fr;
    }

    #secrets-inspector {
        width: 1fr;
    }

    .pending {
        padding: 2;
        border: round #FF6600;
        color: #FF6600;
        background: #190100;
    }

    #footer {
        border-top: solid #00B7FF;
        padding: 0 1;
        background: #00121A;
    }

    #footer-log {
        padding: 0 1;
        color: #6E6E6E;
    }
    """.format(animation=ANIMATION_TIMING)

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("q", "quit", "Quit"),
    ]

    selected_tab: reactive[str] = reactive("overview")

    def compose(self) -> ComposeResult:
        yield HeaderBar()
        yield NavigationBar()
        yield MainPanel()
        yield FooterBar()

    async def on_mount(self) -> None:
        nav = self.query_one(NavigationBar)
        nav.set_active(self.selected_tab)
        header = self.query_one(HeaderBar)
        await header.update_metrics()
        self.set_interval(12.0, header.update_metrics)

    def on_navigation_bar_tab_selected(self, event: NavigationBar.TabSelected) -> None:
        self.selected_tab = event.tab

    def watch_selected_tab(self, tab: str) -> None:
        nav = self.query_one(NavigationBar)
        nav.set_active(tab)
        main = self.query_one(MainPanel)
        main.show_tab(tab)

    def action_quit(self) -> None:
        self.exit()


@lru_cache(maxsize=1)
def get_web3_client() -> Web3:
    rpc = os.getenv(RPC_ENVIRONMENT_VARIABLE)
    if not rpc:
        raise NotImplementedError(
            "Set GNOMAN_ETH_RPC to a valid Ethereum RPC endpoint (HTTPS or IPC) to enable telemetry."
        )
    provider = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 10}))
    if not provider.is_connected():  # pragma: no cover - depends on external RPC
        raise RuntimeError(f"Unable to connect to Ethereum RPC at {rpc}")
    return provider


def fetch_network_metrics() -> NetworkMetrics:
    client = get_web3_client()
    start = time.perf_counter()
    block_number = client.eth.block_number
    latency_ms = (time.perf_counter() - start) * 1000
    try:
        gas_price_wei = client.eth.gas_price
    except (ValueError, Web3Exception):  # pragma: no cover - depends on RPC features
        gas_price_wei = None
    chain_id = None
    try:
        chain_id = client.eth.chain_id
    except (ValueError, Web3Exception):  # pragma: no cover
        chain_id = None
    network_label = f"chain {chain_id}" if chain_id is not None else client.client_version
    gas_price = "—"
    if gas_price_wei is not None:
        gas_price = f"{Decimal(gas_price_wei) / Decimal(10 ** 9):.2f} gwei"
    return NetworkMetrics(
        network_label=network_label,
        block_height=str(block_number),
        gas_price=gas_price,
        latency_ms=f"{latency_ms:.0f} ms",
        timestamp=datetime.now(timezone.utc),
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gnoman",
        description="GNOMAN mission-control console",
    )
    parser.add_argument("--headless", action="store_true", help="Run in automation/headless mode")
    parser.add_argument("--version", action="store_true", help="Display GNOMAN version and exit")
    args = parser.parse_args(argv)

    if args.version:
        print(f"gnoman {__version__}")
        return 0

    if args.headless:
        raise NotImplementedError("Headless automation mode is not implemented yet. Configure mission scripts instead.")

    try:
        append_record("ui.start", {"version": __version__}, True, {"mode": "dashboard"})
    except (NotImplementedError, ValueError):
        pass
    app = NeonControlApp()
    app.run()
    return 0


__all__ = ["NeonControlApp", "main"]

