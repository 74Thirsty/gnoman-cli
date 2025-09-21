"""Mission Control CLI entrypoint for GNOMAN v0.2.0."""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable, Optional

from . import __version__
from .cli import audit, guard, plugin, safe, secrets, tx
from .tui import launch_tui

Handler = Callable[[argparse.Namespace], Any]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gnoman",
        description="GNOMAN mission control CLI",
    )
    parser.add_argument("--version", action="version", version=f"gnoman {__version__}")

    subparsers = parser.add_subparsers(dest="command")

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

    tx_sim = tx_sub.add_parser("simulate", help="Simulate a Safe proposal")
    tx_sim.add_argument("proposal_id", help="Proposal identifier")
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

    # Guard command
    guard_parser = subparsers.add_parser("guard", help="Start the monitoring daemon")
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

    return parser


def main(argv: Optional[list[str]] = None) -> Any:
    argv = sys.argv[1:] if argv is None else argv

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


if __name__ == "__main__":
    main()
