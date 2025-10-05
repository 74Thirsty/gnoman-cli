"""Command line interface for the GNOMAN keyring manager."""

from __future__ import annotations

import argparse
from typing import Any, Iterable, Optional, Sequence

from . import __version__
from .commands import keyring as keyring_commands


def _parse_services(value: Optional[str]) -> Optional[Iterable[str]]:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gnoman",
        description="GNOMAN universal keyring manager",
    )
    parser.add_argument("--version", action="version", version=f"gnoman {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List every keyring entry")
    list_parser.add_argument("--namespace", help="Filter services by prefix")
    list_parser.add_argument(
        "--secrets",
        action="store_true",
        help="Include secret values in the output",
    )
    list_parser.set_defaults(handler=lambda args: keyring_commands.list_entries(args.namespace, args.secrets))

    show_parser = subparsers.add_parser("show", help="Show a single entry")
    show_parser.add_argument("service", help="Service name")
    show_parser.add_argument("username", help="Username or key identifier")
    show_parser.set_defaults(handler=lambda args: keyring_commands.show_entry(args.service, args.username))

    set_parser = subparsers.add_parser("set", help="Create or update an entry")
    set_parser.add_argument("service", help="Service name")
    set_parser.add_argument("username", help="Username or key identifier")
    set_parser.add_argument("value", nargs="?", help="Secret value (prompted when omitted)")
    set_parser.set_defaults(
        handler=lambda args: keyring_commands.set_entry(args.service, args.username, args.value)
    )

    delete_parser = subparsers.add_parser("delete", help="Delete an entry")
    delete_parser.add_argument("service", help="Service name")
    delete_parser.add_argument("username", help="Username or key identifier")
    delete_parser.add_argument("--force", action="store_true", help="Skip the confirmation prompt")
    delete_parser.set_defaults(
        handler=lambda args: keyring_commands.delete_entry(args.service, args.username, args.force)
    )

    export_parser = subparsers.add_parser("export", help="Export the keyring to an encrypted file")
    export_parser.add_argument("path", help="Destination file path")
    export_parser.add_argument("--passphrase", help="Passphrase to use (prompted when omitted)")
    export_parser.set_defaults(
        handler=lambda args: keyring_commands.export_entries(args.path, args.passphrase)
    )

    import_parser = subparsers.add_parser("import", help="Import an encrypted keyring backup")
    import_parser.add_argument("path", help="Path to the encrypted backup")
    import_parser.add_argument("--passphrase", help="Passphrase used during export")
    import_parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace entries even when they already exist",
    )
    import_parser.set_defaults(
        handler=lambda args: keyring_commands.import_entries(args.path, args.passphrase, args.replace)
    )

    rotate_parser = subparsers.add_parser("rotate", help="Rotate stored credentials")
    rotate_parser.add_argument(
        "--services",
        help="Comma separated list of services to rotate (defaults to all)",
    )
    rotate_parser.add_argument(
        "--length",
        type=int,
        default=32,
        help="Generated secret length (in URL-safe characters)",
    )
    rotate_parser.set_defaults(
        handler=lambda args: keyring_commands.rotate_entries(
            services=_parse_services(args.services),
            length=args.length,
        )
    )

    audit_parser = subparsers.add_parser("audit", help="Produce a summary report")
    audit_parser.add_argument(
        "--stale-days",
        type=int,
        default=180,
        help="Consider entries stale after this many days",
    )
    audit_parser.set_defaults(handler=lambda args: keyring_commands.audit(args.stale_days))

    return parser


def main(argv: Optional[Sequence[str]] = None) -> Any:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1
    handler(args)
    return 0
