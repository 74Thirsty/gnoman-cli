"""Minimal curses-based interface scaffolding for GNOMAN v0.2.

This module focuses on rendering the high level views sketched in the design
specification. All data is stubbed/static for now – real Safe/secret plumbing
can replace the `self._demo_*` attributes without touching the view logic.
"""

from __future__ import annotations

import curses
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List

from .logbook import ForensicLogger


class MenuView(Enum):
    MAIN = auto()
    WALLETS = auto()
    SAFES = auto()
    SECRETS = auto()
    TRANSACTIONS = auto()
    PLUGINS = auto()
    AUDIT_GUARD = auto()


@dataclass
class SafeProposal:
    id: int
    description: str
    status: str


@dataclass
class SafeDashboard:
    address: str
    owners: int
    threshold: int
    proposals: List[SafeProposal] = field(default_factory=list)


@dataclass
class SecretEntry:
    key: str
    last_rotated: str
    status: str


class TUIApplication:
    def __init__(self, screen: "curses._CursesWindow", logger: ForensicLogger) -> None:
        self.screen = screen
        self.logger = logger
        self.view = MenuView.MAIN
        self.running = True
        self.message = "Press highlighted keys to navigate."

        self.safe_index = 0
        self.proposal_index = 0
        self.secret_index = 0
        self.plugin_index = 0

        self.safes: List[SafeDashboard] = [
            SafeDashboard(
                address="0xabc…123",
                owners=3,
                threshold=2,
                proposals=[
                    SafeProposal(1, "Send 10 ETH to 0xdef…456", "Pending"),
                    SafeProposal(2, "Upgrade Safe module", "Signed"),
                    SafeProposal(3, "Deploy new guard", "Queued"),
                ],
            ),
            SafeDashboard(
                address="0xfeed…babe",
                owners=4,
                threshold=3,
                proposals=[
                    SafeProposal(7, "Fund payroll multisig", "Pending"),
                    SafeProposal(8, "Swap via CowSwap", "Draft"),
                ],
            ),
        ]

        self.secrets: List[SecretEntry] = [
            SecretEntry("RPC_URL", "2025-09-01", "✅ Active"),
            SecretEntry("SAFE_MASTER", "2025-06-15", "⚠ Expired"),
            SecretEntry("CURVE_ROUTER", "2025-09-20", "✅ Active"),
            SecretEntry("DISCORD_WEBHOOK", "2025-05-11", "⚠ Rotate soon"),
        ]

        self.plugins = ["defi-router", "ml-risk", "withdraw-guard"]

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def run(self) -> None:
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        self.screen.nodelay(False)
        self.screen.keypad(True)

        while self.running:
            self.screen.erase()
            if self.view is MenuView.MAIN:
                self._draw_main_menu()
            elif self.view is MenuView.WALLETS:
                self._draw_wallets()
            elif self.view is MenuView.SAFES:
                self._draw_safes()
            elif self.view is MenuView.SECRETS:
                self._draw_secrets()
            elif self.view is MenuView.TRANSACTIONS:
                self._draw_transactions()
            elif self.view is MenuView.PLUGINS:
                self._draw_plugins()
            elif self.view is MenuView.AUDIT_GUARD:
                self._draw_audit_guard()

            self._draw_status()
            try:
                key = self.screen.getch()
            except KeyboardInterrupt:
                self.logger.log("TUI", "interrupt")
                break
            if key in (ord("q"), ord("Q")) and self.view is MenuView.MAIN:
                self.logger.log("TUI", "exit")
                break
            self._handle_key(key)

    def _format_box(self, title: str, lines: List[str]) -> List[str]:
        content_width = max((len(line) for line in lines), default=0)
        width = max(content_width + 2, len(title) + 4, 48)
        top = f"┌{title:─^{width-2}}┐"
        body = [f"│ {line.ljust(width-3)}│" for line in lines]
        bottom = "└" + "─" * (width - 2) + "┘"
        return [top, *body, bottom]

    def _render_lines(self, lines: List[str], start_y: int = 2, start_x: int = 4) -> None:
        for idx, line in enumerate(lines):
            try:
                self.screen.addstr(start_y + idx, start_x, line)
            except curses.error:
                # Terminal too small; silently ignore drawing errors.
                pass

    def _draw_status(self) -> None:
        try:
            height, width = self.screen.getmaxyx()
            message = self.message[: max(0, width - 4)]
            self.screen.addstr(height - 2, 2, message)
            self.screen.clrtoeol()
        except curses.error:
            pass

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------
    def _draw_main_menu(self) -> None:
        lines = self._format_box(
            " GNOMAN v0.2 ",
            [
                "Wallets     Safes     Secrets     Transactions     Plugins",
                "───────────────────────────────────────────────────────────────",
                "[W] Manage wallets   [S] Manage safes   [C] Manage secrets",
                "[T] Transactions     [P] Plugins        [A] Audit / Guard",
                "                                                  [Q] Quit",
            ],
        )
        self._render_lines(lines)

    def _draw_wallets(self) -> None:
        lines = self._format_box(
            " Wallets ",
            [
                "Wallet manager wiring coming soon.",
                "Use CLI commands to derive, import, and export accounts.",
                "[Q] Back",
            ],
        )
        self._render_lines(lines)

    def _draw_safes(self) -> None:
        safe = self.safes[self.safe_index]
        proposal_lines: List[str] = [
            f"Owners: {safe.owners} (Threshold: {safe.threshold})",
            "────────────────────────────────────────────",
            "Proposals:",
        ]
        for idx, proposal in enumerate(safe.proposals):
            marker = "▶" if idx == self.proposal_index else " "
            summary = f"[{proposal.id}] {proposal.description}".ljust(36)
            proposal_lines.append(f"{marker} {summary} {proposal.status}")
        proposal_lines.extend(
            [
                "────────────────────────────────────────────",
                "[V] View   [S] Sign   [C] Collect   [E] Execute   [M] Simulate",
                "[←][→] Switch Safe   [↑][↓] Select Proposal   [Q] Back",
            ]
        )
        lines = self._format_box(f" SAFE: {safe.address} ", proposal_lines)
        self._render_lines(lines)

    def _draw_secrets(self) -> None:
        header = ["Key              Last Rotated    Status", "─────────────────────────────────────────"]
        rows: List[str] = []
        for idx, entry in enumerate(self.secrets):
            marker = "▶" if idx == self.secret_index else " "
            row = f"{entry.key:<16}{entry.last_rotated:<15}{entry.status}"
            rows.append(f"{marker} {row}")
        rows.extend(
            [
                "─────────────────────────────────────────",
                "[A] Add   [R] Rotate   [D] Delete   [Q] Back",
            ]
        )
        lines = self._format_box(" Secrets ", header + rows)
        self._render_lines(lines)

    def _draw_transactions(self) -> None:
        body = [
            "Proposal #1", "──────────────────────────────", "Target: 0xdef…456", "Value: 10 ETH",
            "Method: transfer()", "──────────────────────────────", "✅ Execution Success",
            "⛽ Gas Estimate: 142,331", "💰 Balance Change: -10 ETH",
            "──────────────────────────────", "[E] Exec Now   [Q/B] Back",
        ]
        lines = self._format_box(" Simulation Result ", body)
        self._render_lines(lines)

    def _draw_plugins(self) -> None:
        rows = ["Installed plugins:"]
        for idx, name in enumerate(self.plugins):
            marker = "▶" if idx == self.plugin_index else " "
            rows.append(f"{marker} {name}")
        rows.extend(
            [
                "──────────────────────────────",
                "[A] Add   [R] Remove   [Q] Back",
            ]
        )
        lines = self._format_box(" Plugins ", rows)
        self._render_lines(lines)

    def _draw_audit_guard(self) -> None:
        lines = self._format_box(
            " Audit & Guard ",
            [
                "[U] Run audit snapshot",
                "[G] Launch guard daemon",
                "Alerts: Discord, Slack, Email",
                "[Q] Back",
            ],
        )
        self._render_lines(lines)

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------
    def _handle_key(self, key: int) -> None:
        if self.view is MenuView.MAIN:
            self._handle_main_key(key)
        elif self.view is MenuView.WALLETS:
            self._handle_wallet_key(key)
        elif self.view is MenuView.SAFES:
            self._handle_safe_key(key)
        elif self.view is MenuView.SECRETS:
            self._handle_secret_key(key)
        elif self.view is MenuView.TRANSACTIONS:
            self._handle_transaction_key(key)
        elif self.view is MenuView.PLUGINS:
            self._handle_plugin_key(key)
        elif self.view is MenuView.AUDIT_GUARD:
            self._handle_audit_key(key)

    def _switch_view(self, view: MenuView) -> None:
        self.view = view
        self.message = f"Switched to {view.name.replace('_', ' ').title()} view."
        self.logger.log("TUI", "view_switch", view=view.name)

    def _handle_main_key(self, key: int) -> None:
        mapping = {
            ord("w"): MenuView.WALLETS,
            ord("W"): MenuView.WALLETS,
            ord("s"): MenuView.SAFES,
            ord("S"): MenuView.SAFES,
            ord("c"): MenuView.SECRETS,
            ord("C"): MenuView.SECRETS,
            ord("t"): MenuView.TRANSACTIONS,
            ord("T"): MenuView.TRANSACTIONS,
            ord("p"): MenuView.PLUGINS,
            ord("P"): MenuView.PLUGINS,
            ord("a"): MenuView.AUDIT_GUARD,
            ord("A"): MenuView.AUDIT_GUARD,
        }
        if key in mapping:
            self._switch_view(mapping[key])
        elif key in (ord("q"), ord("Q")):
            self.running = False

    def _handle_wallet_key(self, key: int) -> None:
        if key in (ord("q"), ord("Q")):
            self._switch_view(MenuView.MAIN)

    def _handle_safe_key(self, key: int) -> None:
        safe = self.safes[self.safe_index]
        proposal = safe.proposals[self.proposal_index]
        if key in (ord("q"), ord("Q")):
            self._switch_view(MenuView.MAIN)
            return
        if key in (curses.KEY_LEFT, ord("h")):
            self.safe_index = (self.safe_index - 1) % len(self.safes)
            self.proposal_index = 0
            self.logger.log("TUI", "safe_cycle", direction="prev", safe=self.safes[self.safe_index].address)
            return
        if key in (curses.KEY_RIGHT, ord("l")):
            self.safe_index = (self.safe_index + 1) % len(self.safes)
            self.proposal_index = 0
            self.logger.log("TUI", "safe_cycle", direction="next", safe=self.safes[self.safe_index].address)
            return
        if key in (curses.KEY_UP, ord("k")):
            self.proposal_index = max(0, self.proposal_index - 1)
            return
        if key in (curses.KEY_DOWN, ord("j")):
            self.proposal_index = min(len(safe.proposals) - 1, self.proposal_index + 1)
            return
        if key in (ord("v"), ord("V")):
            self.message = f"Viewing proposal #{proposal.id}: {proposal.description}"
            self.logger.log("SAFE", "view", proposal_id=proposal.id)
        elif key in (ord("s"), ord("S")):
            self.message = f"Signed proposal #{proposal.id}."
            self.logger.log("SAFE", "sign", proposal_id=proposal.id)
        elif key in (ord("c"), ord("C")):
            self.message = f"Collected signatures for proposal #{proposal.id}."
            self.logger.log("SAFE", "collect", proposal_id=proposal.id)
        elif key in (ord("e"), ord("E")):
            self.message = f"Executing proposal #{proposal.id}."
            self.logger.log("SAFE", "exec", proposal_id=proposal.id)
        elif key in (ord("m"), ord("M")):
            self.message = f"Simulated proposal #{proposal.id}."
            self.logger.log("TX", "simulate", proposal_id=proposal.id)

    def _handle_secret_key(self, key: int) -> None:
        if key in (ord("q"), ord("Q")):
            self._switch_view(MenuView.MAIN)
            return
        if key in (curses.KEY_UP, ord("k")):
            self.secret_index = max(0, self.secret_index - 1)
            return
        if key in (curses.KEY_DOWN, ord("j")):
            self.secret_index = min(len(self.secrets) - 1, self.secret_index + 1)
            return
        entry = self.secrets[self.secret_index]
        if key in (ord("a"), ord("A")):
            self.message = "Add secret placeholder invoked."
            self.logger.log("SECRETS", "add", key=entry.key)
        elif key in (ord("r"), ord("R")):
            self.message = f"Rotate secret {entry.key}."
            self.logger.log("SECRETS", "rotate", key=entry.key)
        elif key in (ord("d"), ord("D")):
            self.message = f"Delete secret {entry.key}."
            self.logger.log("SECRETS", "delete", key=entry.key)

    def _handle_transaction_key(self, key: int) -> None:
        if key in (ord("q"), ord("Q"), ord("b"), ord("B")):
            self._switch_view(MenuView.MAIN)
        elif key in (ord("e"), ord("E")):
            self.message = "Execute-now placeholder triggered."
            self.logger.log("SAFE", "exec", proposal_id=1, via="tui")

    def _handle_plugin_key(self, key: int) -> None:
        if key in (ord("q"), ord("Q")):
            self._switch_view(MenuView.MAIN)
            return
        if key in (curses.KEY_UP, ord("k")):
            self.plugin_index = max(0, self.plugin_index - 1)
            return
        if key in (curses.KEY_DOWN, ord("j")):
            self.plugin_index = min(len(self.plugins) - 1, self.plugin_index + 1)
            return
        name = self.plugins[self.plugin_index]
        if key in (ord("a"), ord("A")):
            self.message = "Add plugin placeholder invoked."
            self.logger.log("PLUGIN", "add", name="new-plugin")
        elif key in (ord("r"), ord("R")):
            self.message = f"Removed plugin {name}."
            self.logger.log("PLUGIN", "remove", name=name)

    def _handle_audit_key(self, key: int) -> None:
        if key in (ord("q"), ord("Q")):
            self._switch_view(MenuView.MAIN)
        elif key in (ord("u"), ord("U")):
            self.message = "Audit snapshot placeholder invoked."
            self.logger.log("AUDIT", "snapshot", via="tui")
        elif key in (ord("g"), ord("G")):
            self.message = "Guard daemon placeholder invoked."
            self.logger.log("GUARD", "start", via="tui")


def run_tui(logger: ForensicLogger) -> None:
    """Launch the curses wrapper with the GNOMAN TUI."""

    def _wrapped(screen: "curses._CursesWindow") -> None:
        app = TUIApplication(screen, logger)
        app.run()

    curses.wrapper(_wrapped)
