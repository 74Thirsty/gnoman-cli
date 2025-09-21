"""Argparse handlers for the GNOMAN v0.2 CLI skeleton.

Each handler currently stubs out the real integrations and simply logs the
intent, which makes it straightforward to wire in the actual Safe/secrets
logic later on. The important piece is that they all call ``logger.log`` so
we always produce forensic output.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .logbook import ForensicLogger

console = Console()


def _status_panel(title: str, body: str) -> None:
    console.print(Panel(body, title=title, border_style="cyan", title_align="left"))


def safe_propose(args, logger: ForensicLogger) -> None:
    logger.log(
        "SAFE",
        "propose",
        status="pending",
        proposal_id="auto",
        to=args.to,
        value=str(args.value),
        data=args.data or "0x",
    )
    _status_panel(
        "Safe proposal queued",
        f"➡️  To: {args.to}\n💰 Value: {args.value} ETH\n🧾 Calldata: {args.data or '0x'}",
    )


def safe_sign(args, logger: ForensicLogger) -> None:
    logger.log("SAFE", "sign", proposal_id=args.proposal_id)
    _status_panel("Proposal signed", f"✍️  Attached signature for proposal #{args.proposal_id}.")


def safe_collect(args, logger: ForensicLogger) -> None:
    logger.log("SAFE", "collect", proposal_id=args.proposal_id)
    _status_panel(
        "Signatures aggregated",
        f"🧮 Combined multisig payload for proposal #{args.proposal_id}.",
    )


def safe_exec(args, logger: ForensicLogger) -> None:
    logger.log("SAFE", "exec", status="submitted", proposal_id=args.proposal_id)
    _status_panel(
        "Execution submitted",
        f"🚀 Proposal #{args.proposal_id} dispatched to the Safe contract.",
    )


def safe_status(args, logger: ForensicLogger) -> None:
    logger.log("SAFE", "status", safe=args.safe_address)
    table = Table(title=f"Safe overview: {args.safe_address}")
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")
    table.add_row("Owners", "3 (Alice, Bob, Charlie)")
    table.add_row("Threshold", "2")
    table.add_row("Next nonce", "42")
    table.add_row("ETH balance", "123.45")

    proposal_table = Table(title="Queued proposals")
    proposal_table.add_column("ID", style="cyan", justify="right")
    proposal_table.add_column("Summary", style="green")
    proposal_table.add_column("Status", style="yellow")
    proposal_table.add_row("1", "Send 10 ETH to 0xdef…456", "Pending")
    proposal_table.add_row("2", "Upgrade Safe module", "Signed")

    console.print(table)
    console.print(proposal_table)


# -- Transactions -----------------------------------------------------------------

def tx_simulate(args, logger: ForensicLogger) -> None:
    logger.log("TX", "simulate", proposal_id=args.proposal_id)
    body = (
        f"✅ Expected execution success\n"
        f"⛽ Gas estimate: 142,331\n"
        f"💰 Value impact: -10 ETH"
    )
    _status_panel(f"Simulation result for proposal #{args.proposal_id}", body)


# -- Secrets -----------------------------------------------------------------------

def secrets_list(args, logger: ForensicLogger) -> None:
    logger.log("SECRETS", "list")
    table = Table(title="Secret inventory (masked)")
    table.add_column("Key", style="cyan")
    table.add_column("Last rotated", style="magenta")
    table.add_column("Status", style="green")
    table.add_row("RPC_URL", "2025-09-01", "✅ Active")
    table.add_row("SAFE_MASTER", "2025-06-15", "⚠ Expired")
    table.add_row("CURVE_ROUTER", "2025-09-20", "✅ Active")
    console.print(table)


def secrets_add(args, logger: ForensicLogger) -> None:
    logger.log("SECRETS", "add", key=args.key, rotation="now")
    _status_panel("Secret stored", f"🔐 Key `{args.key}` captured in keyring.")


def secrets_rotate(args, logger: ForensicLogger) -> None:
    logger.log("SECRETS", "rotate", key=args.key)
    _status_panel("Secret rotation", f"♻️  Key `{args.key}` marked for re-encryption.")


def secrets_audit(args, logger: ForensicLogger) -> None:
    logger.log("SECRETS", "audit")
    _status_panel(
        "Secret audit",
        "🕵️  Checked 12 secrets – 1 expired, 2 expiring soon, alerts dispatched.",
    )


# -- Audit & Guard -----------------------------------------------------------------

def audit_dump(args, logger: ForensicLogger) -> None:
    logger.log("AUDIT", "snapshot")
    _status_panel(
        "Audit report",
        "📊 Generated forensic snapshot: safes=2 wallets=5 secrets=12 thresholds ok.",
    )


def guard_daemon(args, logger: ForensicLogger) -> None:
    logger.log("GUARD", "start", transports=args.transports)
    transports = ", ".join(args.transports) if args.transports else "(none configured)"
    _status_panel(
        "Guard daemon",
        f"🛡 Monitoring chain + secrets. Alerts: {transports}. Press Ctrl+C to exit.",
    )


# -- Plugins -----------------------------------------------------------------------

def plugin_list(args, logger: ForensicLogger) -> None:
    logger.log("PLUGIN", "list")
    table = Table(title="Installed plugins")
    table.add_column("Name", style="cyan")
    table.add_column("Status", style="green")
    table.add_row("defi-router", "Enabled")
    table.add_row("ml-risk", "Disabled")
    console.print(table)


def plugin_add(args, logger: ForensicLogger) -> None:
    logger.log("PLUGIN", "add", name=args.name)
    _status_panel("Plugin installed", f"🔌 Added plugin `{args.name}`.")


def plugin_remove(args, logger: ForensicLogger) -> None:
    logger.log("PLUGIN", "remove", name=args.name)
    _status_panel("Plugin removed", f"🧹 Removed plugin `{args.name}`.")
