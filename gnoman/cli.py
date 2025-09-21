"""GNOMAN mission control CLI entrypoint (v0.2 scaffolding)."""

from __future__ import annotations

import argparse
import sys
from typing import Callable

from rich.console import Console
from rich.panel import Panel

from . import __version__
from . import commands
from .logbook import ForensicLogger, get_logger
from .tui import run_tui

console = Console()


Handler = Callable[[argparse.Namespace, ForensicLogger], None]


def _die(msg: str, code: int = 1) -> None:
    console.print(Panel.fit(f"[bold red]Error[/]: {msg}", border_style="red"))
    raise SystemExit(code)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gnoman",
        description="GNOMAN mission control — Safes, secrets, and simulations.",
    )
    parser.add_argument("--tui", action="store_true", help="Force launch the interactive curses interface.")
    parser.add_argument("--version", action="version", version=f"gnoman {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # -- Safe management ----------------------------------------------------------
    safe = subparsers.add_parser("safe", help="Operate on Gnosis Safe proposals and execution flows.")
    safe_sub = safe.add_subparsers(dest="safe_command")
    safe_sub.required = True

    safe_propose = safe_sub.add_parser("propose", help="Create a new Safe transaction proposal.")
    safe_propose.add_argument("--to", required=True, help="Target address for the Safe call.")
    safe_propose.add_argument("--value", required=True, help="ETH value to send with the proposal.")
    safe_propose.add_argument("--data", default="", help="Hex calldata for the Safe transaction.")
    safe_propose.set_defaults(handler=commands.safe_propose)

    safe_sign = safe_sub.add_parser("sign", help="Sign a pending Safe proposal.")
    safe_sign.add_argument("proposal_id", help="Proposal identifier to sign.")
    safe_sign.set_defaults(handler=commands.safe_sign)

    safe_collect = safe_sub.add_parser("collect", help="Collect multisig signatures for a proposal.")
    safe_collect.add_argument("proposal_id", help="Proposal identifier to aggregate signatures for.")
    safe_collect.set_defaults(handler=commands.safe_collect)

    safe_exec = safe_sub.add_parser("exec", help="Execute a Safe proposal once quorum is met.")
    safe_exec.add_argument("proposal_id", help="Proposal identifier to execute.")
    safe_exec.set_defaults(handler=commands.safe_exec)

    safe_status = safe_sub.add_parser("status", help="Inspect Safe owners, threshold, and queued transactions.")
    safe_status.add_argument("safe_address", help="Safe address to inspect.")
    safe_status.set_defaults(handler=commands.safe_status)

    # -- Transactions -------------------------------------------------------------
    tx = subparsers.add_parser("tx", help="Transaction simulation and tooling.")
    tx_sub = tx.add_subparsers(dest="tx_command")
    tx_sub.required = True

    tx_sim = tx_sub.add_parser("simulate", help="Simulate a proposal on a fork (Hardhat/Anvil).")
    tx_sim.add_argument("proposal_id", help="Proposal identifier to simulate.")
    tx_sim.set_defaults(handler=commands.tx_simulate)

    # -- Secrets -----------------------------------------------------------------
    secrets = subparsers.add_parser("secrets", help="Manage keyring and secure storage entries.")
    secrets_sub = secrets.add_subparsers(dest="secrets_command")
    secrets_sub.required = True

    secrets_list = secrets_sub.add_parser("list", help="Display stored secrets (masked).")
    secrets_list.set_defaults(handler=commands.secrets_list)

    secrets_add = secrets_sub.add_parser("add", help="Store or update a secret in the keyring.")
    secrets_add.add_argument("key", help="Secret name to set.")
    secrets_add.add_argument("value", help="Secret value to persist.")
    secrets_add.set_defaults(handler=commands.secrets_add)

    secrets_rotate = secrets_sub.add_parser("rotate", help="Rotate or re-encrypt a stored secret.")
    secrets_rotate.add_argument("key", help="Secret name to rotate.")
    secrets_rotate.set_defaults(handler=commands.secrets_rotate)

    secrets_audit = secrets_sub.add_parser("audit", help="Audit secrets for staleness or weak configuration.")
    secrets_audit.set_defaults(handler=commands.secrets_audit)

    # -- Audit & Guard ------------------------------------------------------------
    audit = subparsers.add_parser("audit", help="Produce a forensic dump of wallets, safes, and secrets.")
    audit.set_defaults(handler=commands.audit_dump)

    guard = subparsers.add_parser("guard", help="Run the guard daemon to monitor chain + secrets.")
    guard.add_argument(
        "-t",
        "--transport",
        dest="transports",
        action="append",
        help="Alert transport (e.g. discord, slack, email). Repeatable.",
    )
    guard.set_defaults(handler=commands.guard_daemon)

    # -- Plugins ------------------------------------------------------------------
    plugin = subparsers.add_parser("plugin", help="Manage GNOMAN plugin ecosystem.")
    plugin_sub = plugin.add_subparsers(dest="plugin_command")
    plugin_sub.required = True

    plugin_list = plugin_sub.add_parser("list", help="List installed plugins.")
    plugin_list.set_defaults(handler=commands.plugin_list)

    plugin_add = plugin_sub.add_parser("add", help="Install a new plugin by name.")
    plugin_add.add_argument("name", help="Plugin identifier to install.")
    plugin_add.set_defaults(handler=commands.plugin_add)

    plugin_remove = plugin_sub.add_parser("remove", help="Remove an installed plugin.")
    plugin_remove.add_argument("name", help="Plugin identifier to remove.")
    plugin_remove.set_defaults(handler=commands.plugin_remove)

    return parser


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    logger = get_logger()

    if not argv:
        logger.log("TUI", "launch", reason="no_arguments")
        run_tui(logger)
        return

    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        # argparse already printed the message; re-raise to keep exit code.
        raise

    if getattr(args, "tui", False):
        logger.log("TUI", "launch", reason="--tui-flag")
        run_tui(logger)
        return

    handler: Handler | None = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return

    try:
        handler(args, logger)
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/]")
        logger.log("CLI", "interrupt", command=args.command)
    except Exception as exc:  # pragma: no cover - real wiring will handle specifics later
        logger.log("CLI", "error", status="failure", message=str(exc))
        _die(str(exc))


if __name__ == "__main__":
    main()
