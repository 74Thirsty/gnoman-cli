"""Argparse-based command surface for the GNOMAN mission control CLI."""

from __future__ import annotations

import argparse
from typing import Any, Callable, Optional

from . import __version__
from .commands import (
    audit,
    autopilot as autopilot_cmd,
    graph,
    guard,
    plugin,
    rescue,
    safe,
    secrets,
    sync,
    tx,
)
from .tui import launch_tui

Handler = Callable[[argparse.Namespace], Any]


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser with every command surface."""

    parser = argparse.ArgumentParser(
        prog="gnoman",
        description="GNOMAN mission control CLI",
    )
    parser.add_argument("--version", action="version", version=f"gnoman {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # Synchronisation
    sync_parser = subparsers.add_parser("sync", help="Synchronise secrets across environments")
    sync_parser.add_argument("--force", action="store_true", help="Overwrite drift with highest priority values")
    sync_parser.add_argument(
        "--reconcile",
        action="store_true",
        help="Auto-reconcile drift using the AES priority order",
    )
    sync_parser.set_defaults(handler=sync.run)

    # Safe commands
    safe_parser = subparsers.add_parser("safe", help="Safe lifecycle operations")
    safe_sub = safe_parser.add_subparsers(dest="safe_command")
    safe_sub.required = True

    safe_propose = safe_sub.add_parser("propose", help="Propose a Safe transaction")
    safe_propose.add_argument("--to", required=True, help="Recipient address")
    safe_propose.add_argument("--value", required=True, help="ETH amount to send")
    safe_propose.add_argument("--data", default="0x", help="Transaction calldata")
    safe_propose.set_defaults(handler=safe.propose)

    safe_sign = safe_sub.add_parser("sign", help="Sign a Safe proposal")
    safe_sign.add_argument("proposal_id", help="Proposal identifier")
    safe_sign.set_defaults(handler=safe.sign)

    safe_exec = safe_sub.add_parser("exec", help="Execute a Safe proposal")
    safe_exec.add_argument("proposal_id", help="Proposal identifier")
    safe_exec.set_defaults(handler=safe.exec)

    safe_status = safe_sub.add_parser("status", help="Show Safe status")
    safe_status.add_argument("safe_address", help="Safe address to inspect")
    safe_status.set_defaults(handler=safe.status)

    # Transaction commands
    tx_parser = subparsers.add_parser("tx", help="Transaction simulation and execution")
    tx_sub = tx_parser.add_subparsers(dest="tx_command")
    tx_sub.required = True

    tx_sim = tx_sub.add_parser("simulate", help="Simulate a Safe/DeFi transaction plan")
    tx_sim.add_argument("proposal_id", nargs="?", help="Proposal identifier or plan reference")
    tx_sim.add_argument("--plan", help="Path to an execution plan JSON file")
    tx_sim.add_argument("--trace", action="store_true", help="Emit a full execution trace")
    tx_sim.add_argument("--ml-off", action="store_true", help="Bypass the ML scorer stage")
    tx_sim.set_defaults(handler=tx.simulate)

    tx_exec = tx_sub.add_parser("exec", help="Execute a Safe proposal via tx module")
    tx_exec.add_argument("proposal_id", help="Proposal identifier")
    tx_exec.set_defaults(handler=tx.exec)

    # Secrets commands
    secrets_parser = subparsers.add_parser("secrets", help="Manage secrets and keyring entries")
    secrets_sub = secrets_parser.add_subparsers(dest="secrets_command")
    secrets_sub.required = True

    secrets_list = secrets_sub.add_parser("list", help="List stored secrets")
    secrets_list.set_defaults(handler=secrets.list_secrets)

    secrets_add = secrets_sub.add_parser("add", help="Add a secret entry")
    secrets_add.add_argument("key", help="Secret name")
    secrets_add.add_argument("value", help="Secret value")
    secrets_add.set_defaults(handler=secrets.add_secret)

    secrets_rotate = secrets_sub.add_parser("rotate", help="Rotate a secret")
    secrets_rotate.add_argument("key", help="Secret name")
    secrets_rotate.set_defaults(handler=secrets.rotate_secret)

    secrets_remove = secrets_sub.add_parser("rm", help="Remove a secret")
    secrets_remove.add_argument("key", help="Secret name")
    secrets_remove.set_defaults(handler=secrets.remove_secret)

    # Audit command
    audit_parser = subparsers.add_parser("audit", help="Generate a forensic snapshot")
    audit_parser.set_defaults(handler=audit.run)

    # Graph commands
    graph_parser = subparsers.add_parser("graph", help="Visualise routing and liquidity graphs")
    graph_sub = graph_parser.add_subparsers(dest="graph_command")
    graph_sub.required = True

    graph_view = graph_sub.add_parser("view", help="Render the AES graph view")
    graph_view.add_argument(
        "--format",
        choices=["svg", "png", "html"],
        default="svg",
        help="Export format for the rendered graph",
    )
    graph_view.add_argument(
        "--output",
        help="Optional output path. Defaults to ~/.gnoman/graphs",
    )
    graph_view.set_defaults(handler=graph.view)

    # Autopilot command
    autopilot_parser = subparsers.add_parser("autopilot", help="Run the AES autopilot pipeline")
    autopilot_parser.add_argument("--plan", help="Optional path to a trading plan definition")
    autopilot_parser.add_argument("--dry-run", action="store_true", help="Simulate only without broadcast")
    autopilot_parser.add_argument("--execute", action="store_true", help="Broadcast via Safe when complete")
    autopilot_parser.add_argument("--alerts-only", action="store_true", help="Send alerts without execution")
    autopilot_parser.set_defaults(handler=autopilot_cmd.run)

    # Rescue command
    rescue_parser = subparsers.add_parser("rescue", help="Incident recovery utilities")
    rescue_sub = rescue_parser.add_subparsers(dest="rescue_command")
    rescue_sub.required = True

    rescue_safe = rescue_sub.add_parser("safe", help="Launch the Safe recovery wizard")
    rescue_safe.add_argument("safe_address", help="Target Safe address")
    rescue_safe.set_defaults(handler=rescue.rescue_safe)

    # Rotate command
    rotate_parser = subparsers.add_parser("rotate", help="Rotate wallets and signers")
    rotate_sub = rotate_parser.add_subparsers(dest="rotate_command")
    rotate_sub.required = True

    rotate_all = rotate_sub.add_parser("all", help="Rotate all executor wallets and Safe owners")
    rotate_all.set_defaults(handler=rescue.rotate_all)

    # Freeze command
    freeze_parser = subparsers.add_parser("freeze", help="Temporarily freeze a wallet or Safe")
    freeze_parser.add_argument("target_type", choices=["wallet", "safe"], help="Entity type to freeze")
    freeze_parser.add_argument("target_id", help="Wallet address or Safe identifier")
    freeze_parser.add_argument(
        "--reason",
        default="incident response",
        help="Reason to record in the forensic log",
    )
    freeze_parser.set_defaults(handler=rescue.freeze)

    # Guard command
    guard_parser = subparsers.add_parser("guard", help="Start the monitoring daemon")
    guard_parser.add_argument(
        "--cycles",
        type=int,
        default=3,
        help="Number of monitoring cycles to execute before returning",
    )
    guard_parser.set_defaults(handler=guard.run)

    # Plugin commands
    plugin_parser = subparsers.add_parser("plugin", help="Manage plugins")
    plugin_sub = plugin_parser.add_subparsers(dest="plugin_command")
    plugin_sub.required = True

    plugin_list = plugin_sub.add_parser("list", help="List installed plugins")
    plugin_list.set_defaults(handler=plugin.list_plugins)

    plugin_add = plugin_sub.add_parser("add", help="Add a plugin")
    plugin_add.add_argument("name", help="Plugin name")
    plugin_add.set_defaults(handler=plugin.add_plugin)

    plugin_remove = plugin_sub.add_parser("remove", help="Remove a plugin")
    plugin_remove.add_argument("name", help="Plugin name")
    plugin_remove.set_defaults(handler=plugin.remove_plugin)

    plugin_swap = plugin_sub.add_parser("swap", help="Hot-swap a plugin to a new version")
    plugin_swap.add_argument("name", help="Plugin name to hot-swap")
    plugin_swap.add_argument("version", help="Target plugin version")
    plugin_swap.set_defaults(handler=plugin.swap)

    return parser


def main(argv: Optional[list[str]] = None) -> Any:
    """Entry point for ``python -m gnoman`` and ``gnoman`` console script."""

    argv = argv if argv is not None else []
    if not argv:
        # If ``argv`` was supplied as None we need to read from sys.argv lazily to
        # avoid importing ``sys`` at module import time.
        import sys

        argv = sys.argv[1:]

    if not argv:
        launch_tui()
        return None

    parser = build_parser()
    args = parser.parse_args(argv)

    handler: Optional[Handler] = getattr(args, "handler", None)
    if handler is None:
        launch_tui()
        return None

    return handler(args)
