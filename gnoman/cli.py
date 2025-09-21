"""Argparse-based command surface for the GNOMAN mission control CLI."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import __version__
from .abi import AbiManager
from .audit import AuditService
from .core import get_context, shutdown
from .safe import SafeManager, SafeTransaction
from .sync import SecretSyncer
from .wallet import WalletService

Handler = Callable[[argparse.Namespace], Any]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gnoman", description="GNOMAN Safe and wallet orchestration CLI")
    parser.add_argument("--version", action="version", version=f"gnoman {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Safe commands -------------------------------------------------------
    safe_parser = subparsers.add_parser("safe", help="Safe lifecycle operations")
    safe_sub = safe_parser.add_subparsers(dest="safe_command", required=True)

    safe_info = safe_sub.add_parser("info", help="Show Safe status")
    safe_info.set_defaults(handler=handle_safe_info)

    safe_fund = safe_sub.add_parser("fund", help="Send ETH to the Safe with a 24h hold")
    safe_fund.add_argument("amount", type=Decimal, help="Amount of ETH to transfer")
    safe_fund.add_argument("--signer-key", required=True, help="Secret key storing the executor private key")
    safe_fund.set_defaults(handler=handle_safe_fund)

    safe_erc20 = safe_sub.add_parser("erc20", help="Transfer ERC20 tokens into the Safe")
    safe_erc20.add_argument("token", help="Token contract address")
    safe_erc20.add_argument("amount", type=Decimal, help="Token amount")
    safe_erc20.add_argument("--signer-key", required=True, help="Secret key storing the executor private key")
    safe_erc20.set_defaults(handler=handle_safe_erc20)

    safe_add_owner = safe_sub.add_parser("add-owner", help="Add a Safe owner")
    safe_add_owner.add_argument("address", help="Owner address to add")
    safe_add_owner.add_argument("--signer-key", required=True, help="Secret key storing the executor private key")
    safe_add_owner.set_defaults(handler=handle_safe_add_owner)

    safe_remove_owner = safe_sub.add_parser("remove-owner", help="Remove a Safe owner")
    safe_remove_owner.add_argument("address", help="Owner address to remove")
    safe_remove_owner.add_argument("previous", help="Previous owner in the linked list")
    safe_remove_owner.add_argument("--signer-key", required=True, help="Secret key storing the executor private key")
    safe_remove_owner.set_defaults(handler=handle_safe_remove_owner)

    safe_threshold = safe_sub.add_parser("threshold", help="Change Safe threshold")
    safe_threshold.add_argument("value", type=int, help="New threshold value")
    safe_threshold.add_argument("--signer-key", required=True, help="Secret key storing the executor private key")
    safe_threshold.set_defaults(handler=handle_safe_threshold)

    safe_guard = safe_sub.add_parser("guard", help="Guard management")
    guard_sub = safe_guard.add_subparsers(dest="guard_command", required=True)
    guard_show = guard_sub.add_parser("show", help="Display current guard address")
    guard_show.set_defaults(handler=handle_safe_guard_show)
    guard_set = guard_sub.add_parser("set", help="Enable guard")
    guard_set.add_argument("address", help="Delay guard address")
    guard_set.add_argument("--signer-key", required=True, help="Secret key storing the executor private key")
    guard_set.set_defaults(handler=handle_safe_guard_set)
    guard_clear = guard_sub.add_parser("clear", help="Disable guard")
    guard_clear.add_argument("--signer-key", required=True, help="Secret key storing the executor private key")
    guard_clear.set_defaults(handler=handle_safe_guard_clear)

    safe_delegate = safe_sub.add_parser("delegate", help="Delegate registry management")
    delegate_sub = safe_delegate.add_subparsers(dest="delegate_command", required=True)
    delegate_list = delegate_sub.add_parser("list", help="List delegates")
    delegate_list.set_defaults(handler=handle_safe_delegate_list)
    delegate_add = delegate_sub.add_parser("add", help="Add a delegate")
    delegate_add.add_argument("owner", help="Owner address")
    delegate_add.add_argument("delegate", help="Delegate address")
    delegate_add.set_defaults(handler=handle_safe_delegate_add)
    delegate_remove = delegate_sub.add_parser("remove", help="Remove a delegate")
    delegate_remove.add_argument("owner", help="Owner address")
    delegate_remove.add_argument("delegate", help="Delegate address")
    delegate_remove.set_defaults(handler=handle_safe_delegate_remove)

    safe_hold = safe_sub.add_parser("hold", help="Hold queue management")
    hold_sub = safe_hold.add_subparsers(dest="hold_command", required=True)
    hold_list = hold_sub.add_parser("list", help="List pending holds")
    hold_list.set_defaults(handler=handle_safe_hold_list)
    hold_release = hold_sub.add_parser("release", help="Release a hold manually")
    hold_release.add_argument("key", help="Hold key of the form <safe>:<nonce>")
    hold_release.set_defaults(handler=handle_safe_hold_release)

    safe_txhash = safe_sub.add_parser("tx-hash", help="Calculate Safe transaction hash")
    safe_txhash.add_argument("--to", required=True, help="Target address")
    safe_txhash.add_argument("--value", type=int, default=0, help="Wei value")
    safe_txhash.add_argument("--data", default="0x", help="Hex calldata")
    safe_txhash.add_argument("--operation", type=int, default=0, help="Safe operation type")
    safe_txhash.add_argument("--safe-tx-gas", type=int, default=0)
    safe_txhash.add_argument("--base-gas", type=int, default=0)
    safe_txhash.add_argument("--gas-price", type=int, default=0)
    safe_txhash.add_argument("--refund", default="0x0000000000000000000000000000000000000000", help="Refund receiver address")
    safe_txhash.set_defaults(handler=handle_safe_txhash)

    safe_exec = safe_sub.add_parser("exec", help="Execute a Safe transaction")
    safe_exec.add_argument("--to", required=True, help="Target address")
    safe_exec.add_argument("--value", type=int, default=0, help="Wei value")
    safe_exec.add_argument("--data", default="0x", help="Hex calldata")
    safe_exec.add_argument("--operation", type=int, default=0)
    safe_exec.add_argument("--safe-tx-gas", type=int, default=0)
    safe_exec.add_argument("--base-gas", type=int, default=0)
    safe_exec.add_argument("--gas-price", type=int, default=0)
    safe_exec.add_argument("--refund", default="0x0000000000000000000000000000000000000000")
    safe_exec.add_argument("--signature", action="append", dest="signatures", default=[], help="Signature hex string (repeatable)")
    safe_exec.add_argument("--signer-key", required=True, help="Secret key storing the executor private key")
    safe_exec.set_defaults(handler=handle_safe_exec)

    # Wallet commands -----------------------------------------------------
    wallet_parser = subparsers.add_parser("wallet", help="Wallet management")
    wallet_sub = wallet_parser.add_subparsers(dest="wallet_command", required=True)

    wallet_mnemonic = wallet_sub.add_parser("mnemonic", help="Mnemonic operations")
    mnemonic_sub = wallet_mnemonic.add_subparsers(dest="mnemonic_command", required=True)
    mnemonic_generate = mnemonic_sub.add_parser("generate", help="Generate a new mnemonic")
    mnemonic_generate.set_defaults(handler=handle_wallet_generate)
    mnemonic_import = mnemonic_sub.add_parser("import", help="Import an existing mnemonic")
    mnemonic_import.add_argument("mnemonic", help="Space separated mnemonic phrase")
    mnemonic_import.set_defaults(handler=handle_wallet_import)

    wallet_passphrase = wallet_sub.add_parser("passphrase", help="Passphrase management")
    passphrase_sub = wallet_passphrase.add_subparsers(dest="passphrase_command", required=True)
    passphrase_set = passphrase_sub.add_parser("set", help="Set hidden tree passphrase")
    passphrase_set.add_argument("passphrase", help="Passphrase to store")
    passphrase_set.set_defaults(handler=handle_wallet_passphrase_set)
    passphrase_clear = passphrase_sub.add_parser("clear", help="Clear hidden tree passphrase")
    passphrase_clear.set_defaults(handler=handle_wallet_passphrase_clear)

    wallet_sub.add_parser("accounts", help="List derived accounts").set_defaults(handler=handle_wallet_accounts)

    wallet_create = wallet_sub.add_parser("new", help="Create a labelled account")
    wallet_create.add_argument("label", help="Human readable label")
    wallet_create.add_argument("--path", default="default", help="Derivation template")
    wallet_create.set_defaults(handler=handle_wallet_new)

    wallet_scan = wallet_sub.add_parser("scan", help="Scan derivation paths")
    wallet_scan.add_argument("--count", type=int, default=5)
    wallet_scan.add_argument("--hidden", action="store_true")
    wallet_scan.set_defaults(handler=handle_wallet_scan)

    wallet_derive = wallet_sub.add_parser("derive", help="Preview a derivation path")
    wallet_derive.add_argument("path", help="Derivation path or template identifier")
    wallet_derive.set_defaults(handler=handle_wallet_derive)

    wallet_vanity = wallet_sub.add_parser("vanity", help="Run a vanity search")
    wallet_vanity.add_argument("--prefix")
    wallet_vanity.add_argument("--suffix")
    wallet_vanity.add_argument("--regex")
    wallet_vanity.add_argument("--path", default="vanity")
    wallet_vanity.add_argument("--max-attempts", type=int, default=100000)
    wallet_vanity.add_argument("--log-every", type=int, default=5000)
    wallet_vanity.set_defaults(handler=handle_wallet_vanity)

    wallet_label = wallet_sub.add_parser("label", help="Label an address")
    wallet_label.add_argument("address", help="Address to label")
    wallet_label.add_argument("label", help="Label text")
    wallet_label.set_defaults(handler=handle_wallet_label)

    wallet_export = wallet_sub.add_parser("export", help="Export last scan results")
    wallet_export.add_argument("--output", type=Path, help="Output JSON path")
    wallet_export.set_defaults(handler=handle_wallet_export)

    # Sync commands -------------------------------------------------------
    sync_parser = subparsers.add_parser("sync", help="Secret reconciliation")
    sync_sub = sync_parser.add_subparsers(dest="sync_command", required=True)

    sync_status = sync_sub.add_parser("status", help="List secret status")
    sync_status.set_defaults(handler=handle_sync_status)

    sync_drift = sync_sub.add_parser("drift", help="Detect drift between stores")
    sync_drift.set_defaults(handler=handle_sync_drift)

    sync_force = sync_sub.add_parser("force", help="Force priority sync")
    sync_force.set_defaults(handler=handle_sync_force)

    sync_apply = sync_sub.add_parser("apply", help="Apply manual reconciliation")
    sync_apply.add_argument("key", help="Secret key to reconcile")
    sync_apply.add_argument("source", choices=["keyring", "env"], help="Source of truth")
    sync_apply.set_defaults(handler=handle_sync_apply)

    sync_set = sync_sub.add_parser("set", help="Store a secret")
    sync_set.add_argument("key", help="Secret name")
    sync_set.add_argument("value", help="Secret value")
    sync_set.set_defaults(handler=handle_sync_set)

    sync_rotate = sync_sub.add_parser("rotate", help="Rotate a secret")
    sync_rotate.add_argument("key", help="Secret name")
    sync_rotate.set_defaults(handler=handle_sync_rotate)

    sync_remove = sync_sub.add_parser("remove", help="Delete a secret")
    sync_remove.add_argument("key", help="Secret name")
    sync_remove.set_defaults(handler=handle_sync_remove)

    # Audit commands ------------------------------------------------------
    audit_parser = subparsers.add_parser("audit", help="Generate forensic audit")
    audit_parser.set_defaults(handler=handle_audit)

    # ABI commands --------------------------------------------------------
    abi_parser = subparsers.add_parser("abi", help="ABI utilities")
    abi_sub = abi_parser.add_subparsers(dest="abi_command", required=True)

    abi_show = abi_sub.add_parser("show", help="Display Safe ABI summary")
    abi_show.set_defaults(handler=handle_abi_show)

    abi_validate = abi_sub.add_parser("validate", help="Validate ABI JSON payload")
    abi_validate.add_argument("file", type=Path, help="Path to ABI JSON")
    abi_validate.set_defaults(handler=handle_abi_validate)

    abi_encode = abi_sub.add_parser("encode", help="Encode calldata using Safe ABI")
    abi_encode.add_argument("function", help="Function name")
    abi_encode.add_argument("--args", default="[]", help="JSON encoded argument array")
    abi_encode.add_argument("--address", help="Optional contract address for encoding context")
    abi_encode.set_defaults(handler=handle_abi_encode)

    return parser


# -- handlers -------------------------------------------------------------

def handle_safe_info(args: argparse.Namespace) -> Dict[str, Any]:
    manager = SafeManager()
    info = manager.info()
    print(json.dumps(info, indent=2))
    return info


def handle_safe_fund(args: argparse.Namespace) -> Dict[str, Any]:
    manager = SafeManager()
    result = manager.fund_eth(args.amount, signer_key=args.signer_key)
    print(json.dumps(result, indent=2))
    return result


def handle_safe_erc20(args: argparse.Namespace) -> Dict[str, Any]:
    manager = SafeManager()
    result = manager.send_erc20(args.token, args.amount, signer_key=args.signer_key)
    print(json.dumps(result, indent=2))
    return result


def handle_safe_add_owner(args: argparse.Namespace) -> Dict[str, Any]:
    manager = SafeManager()
    result = manager.add_owner(args.address, signer_key=args.signer_key)
    print(json.dumps(result, indent=2))
    return result


def handle_safe_remove_owner(args: argparse.Namespace) -> Dict[str, Any]:
    manager = SafeManager()
    result = manager.remove_owner(args.address, args.previous, signer_key=args.signer_key)
    print(json.dumps(result, indent=2))
    return result


def handle_safe_threshold(args: argparse.Namespace) -> Dict[str, Any]:
    manager = SafeManager()
    result = manager.change_threshold(args.value, signer_key=args.signer_key)
    print(json.dumps(result, indent=2))
    return result


def handle_safe_guard_show(args: argparse.Namespace) -> Dict[str, Any]:
    manager = SafeManager()
    guard = manager.guard()
    payload = {"guard": guard}
    print(json.dumps(payload, indent=2))
    return payload


def handle_safe_guard_set(args: argparse.Namespace) -> Dict[str, Any]:
    manager = SafeManager()
    result = manager.set_guard(args.address, signer_key=args.signer_key)
    print(json.dumps(result, indent=2))
    return result


def handle_safe_guard_clear(args: argparse.Namespace) -> Dict[str, Any]:
    manager = SafeManager()
    result = manager.clear_guard(signer_key=args.signer_key)
    print(json.dumps(result, indent=2))
    return result


def handle_safe_delegate_list(args: argparse.Namespace) -> Dict[str, Any]:
    manager = SafeManager()
    delegates = manager.list_delegates()
    print(json.dumps(delegates, indent=2))
    return delegates


def handle_safe_delegate_add(args: argparse.Namespace) -> Dict[str, Any]:
    manager = SafeManager()
    result = manager.add_delegate(args.owner, args.delegate)
    print(json.dumps(result, indent=2))
    return result


def handle_safe_delegate_remove(args: argparse.Namespace) -> Dict[str, Any]:
    manager = SafeManager()
    result = manager.remove_delegate(args.owner, args.delegate)
    print(json.dumps(result, indent=2))
    return result


def handle_safe_hold_list(args: argparse.Namespace) -> List[Dict[str, Any]]:
    manager = SafeManager()
    holds = manager.hold_entries()
    print(json.dumps(holds, indent=2))
    return holds


def handle_safe_hold_release(args: argparse.Namespace) -> Dict[str, Any]:
    manager = SafeManager()
    manager.release_hold(args.key)
    payload = {"released": args.key}
    print(json.dumps(payload, indent=2))
    return payload


def handle_safe_txhash(args: argparse.Namespace) -> Dict[str, Any]:
    manager = SafeManager()
    transaction = SafeTransaction(
        to=args.to,
        value=args.value,
        data=bytes.fromhex(args.data[2:] if args.data.startswith("0x") else args.data),
        operation=args.operation,
        safe_tx_gas=args.safe_tx_gas,
        base_gas=args.base_gas,
        gas_price=args.gas_price,
        refund_receiver=args.refund,
    )
    payload = manager.build_safe_transaction(transaction)
    print(json.dumps(payload, indent=2))
    return payload


def handle_safe_exec(args: argparse.Namespace) -> Dict[str, Any]:
    manager = SafeManager()
    transaction = SafeTransaction(
        to=args.to,
        value=args.value,
        data=bytes.fromhex(args.data[2:] if args.data.startswith("0x") else args.data),
        operation=args.operation,
        safe_tx_gas=args.safe_tx_gas,
        base_gas=args.base_gas,
        gas_price=args.gas_price,
        refund_receiver=args.refund,
    )
    payload = manager.exec_safe_transaction(transaction, args.signatures, signer_key=args.signer_key)
    print(json.dumps(payload, indent=2))
    return payload


# Wallet handlers ---------------------------------------------------------

def handle_wallet_generate(args: argparse.Namespace) -> Dict[str, Any]:
    service = WalletService()
    payload = service.generate_mnemonic()
    print(json.dumps({"default_address": payload["default_address"], "path": payload["path"]}, indent=2))
    return payload


def handle_wallet_import(args: argparse.Namespace) -> Dict[str, Any]:
    service = WalletService()
    payload = service.import_mnemonic(args.mnemonic)
    print(json.dumps(payload, indent=2))
    return payload


def handle_wallet_passphrase_set(args: argparse.Namespace) -> Dict[str, Any]:
    service = WalletService()
    service.set_passphrase(args.passphrase)
    payload = {"passphrase": "set"}
    print(json.dumps(payload, indent=2))
    return payload


def handle_wallet_passphrase_clear(args: argparse.Namespace) -> Dict[str, Any]:
    service = WalletService()
    service.clear_passphrase()
    payload = {"passphrase": "cleared"}
    print(json.dumps(payload, indent=2))
    return payload


def handle_wallet_accounts(args: argparse.Namespace) -> Dict[str, Any]:
    service = WalletService()
    accounts = service.list_accounts()
    print(json.dumps(accounts, indent=2))
    return {"accounts": accounts}


def handle_wallet_new(args: argparse.Namespace) -> Dict[str, Any]:
    service = WalletService()
    record = service.create_account(args.label, path=args.path)
    print(json.dumps(record, indent=2))
    return record


def handle_wallet_scan(args: argparse.Namespace) -> Dict[str, Any]:
    service = WalletService()
    discovered = service.scan(args.count, hidden=args.hidden)
    print(json.dumps(discovered, indent=2))
    return {"discovered": discovered}


def handle_wallet_derive(args: argparse.Namespace) -> Dict[str, Any]:
    service = WalletService()
    payload = service.derive(args.path)
    print(json.dumps(payload, indent=2))
    return payload


def handle_wallet_vanity(args: argparse.Namespace) -> Dict[str, Any]:
    service = WalletService()
    payload = service.find_vanity(
        prefix=args.prefix,
        suffix=args.suffix,
        regex=args.regex,
        path=args.path,
        max_attempts=args.max_attempts,
        log_every=args.log_every,
    )
    print(json.dumps(payload, indent=2))
    return payload


def handle_wallet_label(args: argparse.Namespace) -> Dict[str, Any]:
    service = WalletService()
    service.label_address(args.address, args.label)
    payload = {"labelled": args.address, "label": args.label}
    print(json.dumps(payload, indent=2))
    return payload


def handle_wallet_export(args: argparse.Namespace) -> Dict[str, Any]:
    service = WalletService()
    path = service.export_discovered(args.output)
    payload = {"exported": str(path)}
    print(json.dumps(payload, indent=2))
    return payload


# Sync handlers -----------------------------------------------------------

def handle_sync_status(args: argparse.Namespace) -> Dict[str, Any]:
    syncer = SecretSyncer()
    records = syncer.list_status()
    print(json.dumps(records, indent=2))
    return {"secrets": records}


def handle_sync_drift(args: argparse.Namespace) -> Dict[str, Any]:
    syncer = SecretSyncer()
    drift = syncer.detect_drift()
    print(json.dumps(drift, indent=2))
    return drift


def handle_sync_force(args: argparse.Namespace) -> Dict[str, Any]:
    syncer = SecretSyncer()
    actions = syncer.force_sync()
    print(json.dumps(actions, indent=2))
    return {"actions": actions}


def handle_sync_apply(args: argparse.Namespace) -> Dict[str, Any]:
    syncer = SecretSyncer()
    actions = syncer.apply_decisions({args.key: args.source})
    print(json.dumps(actions, indent=2))
    return {"actions": actions}


def handle_sync_set(args: argparse.Namespace) -> Dict[str, Any]:
    syncer = SecretSyncer()
    syncer.set_secret(args.key, args.value)
    payload = {"stored": args.key}
    print(json.dumps(payload, indent=2))
    return payload


def handle_sync_rotate(args: argparse.Namespace) -> Dict[str, Any]:
    syncer = SecretSyncer()
    value = syncer.rotate_secret(args.key)
    payload = {"rotated": args.key, "preview": value[:4] + "***"}
    print(json.dumps(payload, indent=2))
    return payload


def handle_sync_remove(args: argparse.Namespace) -> Dict[str, Any]:
    syncer = SecretSyncer()
    syncer.remove_secret(args.key)
    payload = {"removed": args.key}
    print(json.dumps(payload, indent=2))
    return payload


# Audit handlers ----------------------------------------------------------

def handle_audit(args: argparse.Namespace) -> Dict[str, Any]:
    service = AuditService()
    report = service.generate()
    payload = {"json": str(report.json_path), "pdf": str(report.pdf_path), "signature": report.signature}
    print(json.dumps(payload, indent=2))
    return payload


# ABI handlers ------------------------------------------------------------

def handle_abi_show(args: argparse.Namespace) -> Dict[str, Any]:
    manager = AbiManager()
    summary = manager.describe()
    print(json.dumps(summary, indent=2))
    return summary


def handle_abi_validate(args: argparse.Namespace) -> Dict[str, Any]:
    manager = AbiManager()
    summary = manager.validate_file(args.file)
    print(json.dumps(summary, indent=2))
    return summary


def handle_abi_encode(args: argparse.Namespace) -> Dict[str, Any]:
    manager = AbiManager()
    try:
        parsed_args: List[Any] = json.loads(args.args)
    except json.JSONDecodeError as exc:  # pragma: no cover - CLI validation
        raise SystemExit(f"Invalid args JSON: {exc}")
    payload = manager.encode(args.function, parsed_args, address=args.address)
    print(json.dumps(payload, indent=2))
    return payload


# Entrypoint --------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> Any:
    parser = build_parser()
    args = parser.parse_args(argv)
    context = get_context()
    try:
        handler: Handler = args.handler  # type: ignore[attr-defined]
    except AttributeError:  # pragma: no cover - argparse guard
        parser.print_help()
        return 1
    try:
        return handler(args)
    except Exception as exc:
        context.ledger.log("cli_exception", params={"command": args.command}, ok=False, severity="ERROR", result={"error": str(exc)})
        context.logger.exception("Unhandled CLI error: %s", exc)
        raise
    finally:
        shutdown()


if __name__ == "__main__":  # pragma: no cover
    main()
