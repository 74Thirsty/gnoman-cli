"""Headless automation CLI for GNOMAN."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

from . import __version__
from .core import AuditManager, ContractManager, SafeManager, SecretsManager, SyncManager, WalletManager


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gnomanctl", description="GNOMAN headless control surface")
    parser.add_argument("--version", action="store_true", help="Display version information and exit")
    subparsers = parser.add_subparsers(dest="command")

    # Secrets ------------------------------------------------------------
    secrets = subparsers.add_parser("secrets", help="Manage system keyring secrets")
    secrets_sub = secrets.add_subparsers(dest="secrets_command")

    secrets_list = secrets_sub.add_parser("list", help="List secrets")
    secrets_list.add_argument("--namespace", help="Filter by service namespace", default=None)
    secrets_list.add_argument("--values", action="store_true", help="Include secret values")

    secrets_add = secrets_sub.add_parser("add", help="Store a secret")
    secrets_add.add_argument("service")
    secrets_add.add_argument("username")
    secrets_add.add_argument("secret")

    secrets_delete = secrets_sub.add_parser("delete", help="Delete a secret")
    secrets_delete.add_argument("service")
    secrets_delete.add_argument("username")

    secrets_rotate = secrets_sub.add_parser("rotate", help="Rotate secrets")
    secrets_rotate.add_argument("--service", action="append", dest="services", help="Restrict rotation to service")
    secrets_rotate.add_argument("--length", type=int, default=32, help="Generated secret length")

    # Wallets ------------------------------------------------------------
    wallets = subparsers.add_parser("wallet", help="HD wallet management")
    wallet_sub = wallets.add_subparsers(dest="wallet_command")

    wallet_list = wallet_sub.add_parser("list", help="List managed wallets")

    wallet_create = wallet_sub.add_parser("create", help="Create a wallet")
    wallet_create.add_argument("label")
    wallet_create.add_argument("--path", default=None, dest="path", help="Derivation path")
    wallet_create.add_argument("--passphrase", default="", help="Mnemonic passphrase")

    wallet_import = wallet_sub.add_parser("import", help="Import from mnemonic")
    wallet_import.add_argument("label")
    wallet_import.add_argument("mnemonic")
    wallet_import.add_argument("--path", default=None)
    wallet_import.add_argument("--passphrase", default="")

    wallet_export = wallet_sub.add_parser("export", help="Export encrypted backup")
    wallet_export.add_argument("label")
    wallet_export.add_argument("path")
    wallet_export.add_argument("passphrase")

    wallet_backup_import = wallet_sub.add_parser("import-backup", help="Import from encrypted backup")
    wallet_backup_import.add_argument("path")
    wallet_backup_import.add_argument("passphrase")

    wallet_sign = wallet_sub.add_parser("sign", help="Sign a message")
    wallet_sign.add_argument("label")
    wallet_sign.add_argument("message")

    wallet_balance = wallet_sub.add_parser("balance", help="Query wallet balance")
    wallet_balance.add_argument("label")

    # Audit --------------------------------------------------------------
    audit = subparsers.add_parser("audit", help="Generate audit reports")
    audit.add_argument("--output", help="Optional output path")
    audit.add_argument("--encrypt", help="Encrypt report with passphrase")

    # Sync ---------------------------------------------------------------
    sync = subparsers.add_parser("sync", help="Reconcile .env/.env.secure with keyring")
    sync.add_argument("--root", help="Project root", default=None)
    sync.add_argument("--no-env", action="store_true", help="Do not update .env.secure")
    sync.add_argument("--no-keyring", action="store_true", help="Do not update keyring")

    # Contracts ----------------------------------------------------------
    contracts = subparsers.add_parser("contract", help="Inspect contract ABIs")
    contracts.add_argument("path")
    contracts.add_argument("--name")
    contracts.add_argument("--address")

    # Safes --------------------------------------------------------------
    safes = subparsers.add_parser("safe", help="Operate Gnosis Safes")
    safe_sub = safes.add_subparsers(dest="safe_command")

    safe_deploy = safe_sub.add_parser("deploy", help="Deploy a new Safe")
    safe_deploy.add_argument("owners", nargs="+", help="Owner addresses")
    safe_deploy.add_argument("--threshold", type=int)

    safe_owner = safe_sub.add_parser("owners", help="Modify Safe owners")
    safe_owner.add_argument("safe")
    safe_owner.add_argument("--add")
    safe_owner.add_argument("--remove")
    safe_owner.add_argument("--threshold", type=int)

    safe_tx = safe_sub.add_parser("tx", help="Create a Safe transaction")
    safe_tx.add_argument("safe")
    safe_tx.add_argument("to")
    safe_tx.add_argument("value", type=int)
    safe_tx.add_argument("--data", default="0x")
    safe_tx.add_argument("--operation", type=int, default=0)

    return parser


def _handle_secrets(args: argparse.Namespace) -> Any:
    manager = SecretsManager()
    command = args.secrets_command
    if command == "list":
        records = manager.list(namespace=args.namespace, include_values=args.values)
        return [record.__dict__ for record in records]
    if command == "add":
        manager.add(service=args.service, username=args.username, secret=args.secret)
        return {"status": "added"}
    if command == "delete":
        manager.delete(service=args.service, username=args.username)
        return {"status": "deleted"}
    if command == "rotate":
        count = manager.rotate(services=args.services, length=args.length)
        return {"rotated": count}
    raise ValueError("Unknown secrets command")


def _handle_wallet(args: argparse.Namespace) -> Any:
    manager = WalletManager()
    command = args.wallet_command
    if command == "list":
        return [
            {
                "label": record.label,
                "address": record.address,
                "derivation_path": record.derivation_path,
                "created": record.created.isoformat(),
                "modified": record.modified.isoformat(),
            }
            for record in manager.list_wallets()
        ]
    default_path = "m/44'/60'/0'/0/0"
    if command == "create":
        record = manager.create_wallet(
            label=args.label,
            derivation_path=args.path or default_path,
            passphrase=args.passphrase,
        )
        return {"label": record.label, "address": record.address}
    if command == "import":
        record = manager.import_wallet(
            label=args.label,
            mnemonic=args.mnemonic,
            derivation_path=args.path or default_path,
            passphrase=args.passphrase,
        )
        return {"label": record.label, "address": record.address}
    if command == "export":
        path = manager.export_wallet(label=args.label, path=Path(args.path), passphrase=args.passphrase)
        return {"path": str(path)}
    if command == "import-backup":
        record = manager.import_backup(path=Path(args.path), passphrase=args.passphrase)
        return {"label": record.label, "address": record.address}
    if command == "sign":
        signature = manager.sign_message(label=args.label, message=args.message)
        return {"signature": signature}
    if command == "balance":
        return manager.balance(label=args.label)
    raise ValueError("Unknown wallet command")


def _handle_audit(args: argparse.Namespace) -> Any:
    manager = AuditManager()
    path = manager.run_audit(output=args.output, encrypt_passphrase=args.encrypt)
    return {"path": str(path)}


def _handle_sync(args: argparse.Namespace) -> Any:
    root = Path(args.root) if args.root else None
    manager = SyncManager(root=root)
    report = manager.reconcile(update_env=not args.no_env, update_keyring=not args.no_keyring)
    return {
        "env_only": report.env_only,
        "secure_only": report.secure_only,
        "keyring_only": report.keyring_only,
        "mismatched": report.mismatched,
    }


def _handle_contract(args: argparse.Namespace) -> Any:
    manager = ContractManager()
    summary = manager.load_contract(path=args.path, name=args.name, address=args.address)
    return {
        "name": summary.name,
        "path": str(summary.path),
        "address": summary.address,
        "functions": summary.functions,
    }


def _handle_safe(args: argparse.Namespace) -> Any:
    manager = SafeManager()
    command = args.safe_command
    if command == "deploy":
        result = manager.deploy_safe(owners=args.owners, threshold=args.threshold)
        return {"address": result.address, "tx_hash": result.tx_hash}
    if command == "owners":
        tx_hash = manager.manage_owners(
            safe_address=args.safe,
            add_owner=args.add,
            remove_owner=args.remove,
            threshold=args.threshold,
        )
        return {"tx_hash": tx_hash}
    if command == "tx":
        data = bytes.fromhex(args.data[2:]) if args.data.startswith("0x") else args.data.encode("utf-8")
        tx_hash = manager.handle_transaction(
            safe_address=args.safe,
            to=args.to,
            value=args.value,
            data=data,
            operation=args.operation,
        )
        return {"tx_hash": tx_hash}
    raise ValueError("Unknown safe command")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(f"gnomanctl {__version__}")
        return 0
    if args.command is None:
        parser.print_help()
        return 1
    handlers = {
        "secrets": _handle_secrets,
        "wallet": _handle_wallet,
        "audit": _handle_audit,
        "sync": _handle_sync,
        "contract": _handle_contract,
        "safe": _handle_safe,
    }
    handler = handlers[args.command]
    result = handler(args)
    if result is not None:
        json.dump(result, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    return 0


__all__ = ["main"]

