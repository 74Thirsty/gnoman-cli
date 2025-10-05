"""Argparse CLI exposing the GNOMAN mission control surface."""

from __future__ import annotations

import argparse
from typing import Any, Callable, Optional, Sequence

from . import __version__
from .commands import (
    audit,
    recover,
    safe,
    secrets,
    wallet,
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

    # Recover command
    recover_parser = subparsers.add_parser("recover", help="Incident recovery utilities")
    recover_sub = recover_parser.add_subparsers(dest="recover_command")
    recover_sub.required = True

    recover_safe = recover_sub.add_parser("safe", help="Launch the Safe recovery wizard")
    recover_safe.add_argument("safe_address", help="Target Safe address")
    recover_safe.set_defaults(handler=recover.recover_safe)

    recover_rotate = recover_sub.add_parser("rotate", help="Rotate executor wallets and Safe owners")
    recover_rotate.set_defaults(handler=recover.rotate_all)

    recover_freeze = recover_sub.add_parser("freeze", help="Temporarily freeze a wallet or Safe")
    recover_freeze.add_argument("target_type", choices=["wallet", "safe"], help="Entity type to freeze")
    recover_freeze.add_argument("target_id", help="Wallet address or Safe identifier")
    recover_freeze.add_argument(
        "--reason",
        default="incident response",
        help="Reason to record in the forensic log",
    )
    recover_freeze.set_defaults(handler=recover.freeze)

    # Wallet commands
    wallet_parser = subparsers.add_parser("wallet", help="HD wallet management")
    wallet_sub = wallet_parser.add_subparsers(dest="wallet_command")
    wallet_sub.required = True

    wallet_new = wallet_sub.add_parser("new", help="Derive a new account from the configured seed")
    wallet_new.add_argument("--label", required=True, help="Label for the derived account")
    wallet_new.add_argument(
        "--path",
        default="default",
        help="Derivation path name or explicit template (defaults to 'default')",
    )
    wallet_new.set_defaults(handler=wallet.new)

    wallet_list = wallet_sub.add_parser("list", help="List derived accounts")
    wallet_list.set_defaults(handler=wallet.list_accounts)

    wallet_passphrase = wallet_sub.add_parser(
        "passphrase", help="Set or clear the encrypted wallet passphrase"
    )
    wallet_passphrase.add_argument(
        "--passphrase",
        help="Passphrase value (omit to be prompted interactively)",
    )
    wallet_passphrase.add_argument(
        "--clear",
        action="store_true",
        help="Clear the stored passphrase (renders encrypted stores inaccessible)",
    )
    wallet_passphrase.set_defaults(handler=wallet.set_passphrase)

    wallet_vanity = wallet_sub.add_parser("vanity", help="Search for a vanity address")
    wallet_vanity.add_argument("--prefix", help="Hex prefix to match (case-insensitive)")
    wallet_vanity.add_argument("--suffix", help="Hex suffix to match (case-insensitive)")
    wallet_vanity.add_argument("--regex", help="Regular expression to match against the address")
    wallet_vanity.add_argument(
        "--path",
        default="vanity",
        help="Derivation path name or template used during the search",
    )
    wallet_vanity.add_argument(
        "--max-attempts",
        type=int,
        default=1_000_000,
        help="Maximum attempts before aborting the vanity search",
    )
    wallet_vanity.add_argument(
        "--log-every",
        type=int,
        default=5_000,
        help="Emit a progress log every N attempts",
    )
    wallet_vanity.set_defaults(handler=wallet.vanity)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> Any:
    """Entry point for ``python -m gnoman`` and ``gnoman`` console script."""

    if argv is None:
        import sys

        tokens: list[str] = sys.argv[1:]
    else:
        tokens = list(argv)

    if not tokens:
        launch_tui()
        return None

    parser = build_parser()
    args = parser.parse_args(tokens)

    handler: Optional[Handler] = getattr(args, "handler", None)
    if handler is None:
        launch_tui()
        return None

    return handler(args)
