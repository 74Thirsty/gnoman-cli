"""Prompt Toolkit powered mission control interface for GNOMAN."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Optional

from prompt_toolkit.shortcuts import button_dialog, input_dialog, message_dialog
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider

from ..core import (
    AuditManager,
    ContractManager,
    SafeManager,
    SecretsManager,
    SyncManager,
    WalletManager,
)
from ..core.sync_manager import SyncReport
from ..core.wallet_manager import DEFAULT_DERIVATION_PATH
from ..utils import keyring_backend
from ..core import abi_manager


class TerminalUI:
    """High level orchestration for the interactive terminal dashboard."""

    MAIN_MENU = [
        ("Secrets Vault", "secrets"),
        ("Wallet Hangar", "wallets"),
        ("Safe Operations", "safes"),
        ("Contracts & ABI Lab", "contracts"),
        ("Audit Forge", "audit"),
        ("Sync Recon", "sync"),
        ("Quit", "quit"),
    ]

    def __init__(self, *, console: Optional[Console] = None) -> None:
        self.console = console or Console(highlight=False)
        self.secrets = SecretsManager()
        self.wallets = WalletManager()
        self.safes = SafeManager()
        self.contracts = ContractManager()
        self.audit = AuditManager()
        self.sync = SyncManager()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @property
    def main_menu_labels(self) -> List[str]:
        """Expose the menu labels for testing and telemetry."""

        return [label for label, _ in self.MAIN_MENU]

    def run(self) -> None:
        """Launch the interactive menu loop."""

        while True:
            choice = button_dialog(
                title="GNOMAN Mission Control",
                text="Select a subsystem to operate.",
                buttons=[(label, value) for label, value in self.MAIN_MENU],
            ).run()
            if choice in (None, "quit"):
                break
            handler = getattr(self, f"_handle_{choice}", None)
            if handler is None:
                self._show_message("Unavailable", f"No handler for action '{choice}'.")
                continue
            try:
                handler()
            except KeyboardInterrupt:
                break
            except Exception as exc:  # pragma: no cover - defensive UI guard
                self._show_message("Error", f"{type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------
    # UI primitives
    # ------------------------------------------------------------------
    def _prompt_text(
        self,
        title: str,
        text: str,
        *,
        password: bool = False,
        default: Optional[str] = None,
    ) -> Optional[str]:
        dialog = input_dialog(title=title, text=text, password=password, default=default or "")
        result = dialog.run()
        if result is None:
            return None
        return result.strip()

    def _prompt_confirm(self, title: str, text: str) -> bool:
        return bool(
            button_dialog(title=title, text=text, buttons=[("Yes", True), ("No", False)]).run()
        )

    def _show_message(self, title: str, text: str) -> None:
        message_dialog(title=title, text=text).run()

    def _show_panel(self, title: str, renderable) -> None:
        with self.console.capture() as capture:
            self.console.print(Panel(renderable, title=title, title_align="left"))
        message_dialog(title=title, text=capture.get()).run()

    def _render_table(self, title: str, table: Table) -> None:
        with self.console.capture() as capture:
            self.console.print(table)
        message_dialog(title=title, text=capture.get()).run()

    def _render_sync_report(self, report: SyncReport) -> None:
        table = Table(title="Sync Variance", show_lines=True)
        table.add_column("Bucket", style="cyan", justify="left")
        table.add_column("Entries", style="magenta")
        table.add_row("env_only", json.dumps(report.env_only, indent=2, ensure_ascii=False))
        table.add_row("secure_only", json.dumps(report.secure_only, indent=2, ensure_ascii=False))
        table.add_row("keyring_only", json.dumps(report.keyring_only, indent=2, ensure_ascii=False))
        table.add_row("mismatched", json.dumps(report.mismatched, indent=2, ensure_ascii=False))
        self._render_table("Sync Recon", table)

    # ------------------------------------------------------------------
    # Secrets
    # ------------------------------------------------------------------
    def _handle_secrets(self) -> None:
        while True:
            choice = button_dialog(
                title="Secrets Vault",
                text="Manage stored credentials.",
                buttons=[
                    ("List Secrets", "list"),
                    ("Add Secret", "add"),
                    ("Delete Secret", "delete"),
                    ("Rotate", "rotate"),
                    ("Back", "back"),
                ],
            ).run()
            if choice in (None, "back"):
                return
            if choice == "list":
                records = self.secrets.list(include_values=True)
                table = Table(title="Stored Secrets", show_header=True, header_style="bold")
                table.add_column("Service", style="cyan")
                table.add_column("User", style="green")
                table.add_column("Secret", style="yellow")
                for record in records:
                    table.add_row(record.service, record.username, record.secret or "•" * 4)
                if not records:
                    self._show_message("Secrets", "No secrets stored in the keyring.")
                else:
                    self._render_table("Secrets", table)
            elif choice == "add":
                service = self._prompt_text("Secrets", "Service namespace")
                if not service:
                    continue
                username = self._prompt_text("Secrets", "Username")
                if not username:
                    continue
                secret = self._prompt_text("Secrets", "Secret", password=True)
                if secret is None:
                    continue
                self.secrets.add(service=service, username=username, secret=secret)
                self._show_message("Secrets", f"Stored credential for {service}/{username}.")
            elif choice == "delete":
                service = self._prompt_text("Secrets", "Service namespace")
                if not service:
                    continue
                username = self._prompt_text("Secrets", "Username")
                if not username:
                    continue
                if self._prompt_confirm(
                    "Confirm delete", f"Remove secret for {service}/{username}?"
                ):
                    self.secrets.delete(service=service, username=username)
                    self._show_message("Secrets", "Secret removed.")
            elif choice == "rotate":
                services = self._prompt_text(
                    "Secrets", "Comma separated service names (blank for all)"
                )
                selected: Optional[Iterable[str]]
                if services:
                    selected = [item.strip() for item in services.split(",") if item.strip()]
                else:
                    selected = None
                length_text = self._prompt_text("Secrets", "Generated length", default="32")
                length = int(length_text or "32")
                updated = self.secrets.rotate(services=selected, length=length)
                self._show_message("Secrets", f"Rotated {updated} secret(s).")

    # ------------------------------------------------------------------
    # Wallets
    # ------------------------------------------------------------------
    def _handle_wallets(self) -> None:
        while True:
            choice = button_dialog(
                title="Wallet Hangar",
                text="HD wallet operations.",
                buttons=[
                    ("List Wallets", "list"),
                    ("Create Wallet", "create"),
                    ("Import Mnemonic", "import"),
                    ("Export Backup", "export"),
                    ("Import Backup", "restore"),
                    ("Sign Message", "sign"),
                    ("Balance", "balance"),
                    ("Vanity Search", "vanity"),
                    ("Back", "back"),
                ],
            ).run()
            if choice in (None, "back"):
                return
            try:
                if choice == "list":
                    records = self.wallets.list_wallets()
                    table = Table(title="Wallet Inventory", show_lines=True)
                    table.add_column("Label", style="cyan")
                    table.add_column("Address", style="green")
                    table.add_column("Derivation", style="magenta")
                    table.add_column("Network", style="yellow")
                    for record in records:
                        table.add_row(
                            record.label,
                            record.address,
                            record.derivation_path,
                            record.network or "—",
                        )
                    if not records:
                        self._show_message("Wallets", "No wallets have been provisioned yet.")
                    else:
                        self._render_table("Wallets", table)
                elif choice == "create":
                    label = self._prompt_text("Create Wallet", "Wallet label")
                    if not label:
                        continue
                    derivation = self._prompt_text(
                        "Create Wallet",
                        "Derivation path",
                        default=DEFAULT_DERIVATION_PATH,
                    ) or DEFAULT_DERIVATION_PATH
                    passphrase = self._prompt_text(
                        "Create Wallet", "Mnemonic passphrase (optional)", password=True
                    ) or ""
                    network = self._prompt_text(
                        "Create Wallet", "Network label (optional)"
                    )
                    record = self.wallets.create_wallet(
                        label=label,
                        derivation_path=derivation,
                        passphrase=passphrase,
                        network=network or None,
                    )
                    details = Text(
                        f"Label: {record.label}\nAddress: {record.address}\nDerivation: {record.derivation_path}",
                        style="green",
                    )
                    self._show_panel("Wallet Created", details)
                elif choice == "import":
                    label = self._prompt_text("Import Wallet", "Wallet label")
                    if not label:
                        continue
                    mnemonic = self._prompt_text(
                        "Import Wallet", "BIP39 mnemonic", default=""
                    )
                    if not mnemonic:
                        continue
                    derivation = self._prompt_text(
                        "Import Wallet",
                        "Derivation path",
                        default=DEFAULT_DERIVATION_PATH,
                    ) or DEFAULT_DERIVATION_PATH
                    passphrase = self._prompt_text(
                        "Import Wallet", "Mnemonic passphrase", password=True
                    ) or ""
                    network = self._prompt_text(
                        "Import Wallet", "Network label (optional)"
                    )
                    record = self.wallets.import_wallet(
                        label=label,
                        mnemonic=mnemonic,
                        derivation_path=derivation,
                        passphrase=passphrase,
                        network=network or None,
                    )
                    self._show_message(
                        "Wallet Imported", f"Wallet {record.label} bound to {record.address}."
                    )
                elif choice == "export":
                    label = self._prompt_text("Export Wallet", "Wallet label")
                    if not label:
                        continue
                    path_text = self._prompt_text(
                        "Export Wallet", "Destination path", default=str(Path.home())
                    )
                    if not path_text:
                        continue
                    dest = Path(path_text).expanduser()
                    passphrase = self._prompt_text(
                        "Export Wallet", "Encryption passphrase", password=True
                    )
                    if passphrase is None:
                        continue
                    written = self.wallets.export_wallet(label=label, path=dest, passphrase=passphrase)
                    self._show_message("Wallet Export", f"Encrypted backup written to {written}.")
                elif choice == "restore":
                    path_text = self._prompt_text("Restore Wallet", "Backup path")
                    if not path_text:
                        continue
                    source = Path(path_text).expanduser()
                    passphrase = self._prompt_text(
                        "Restore Wallet", "Decryption passphrase", password=True
                    )
                    if passphrase is None:
                        continue
                    record = self.wallets.import_backup(path=source, passphrase=passphrase)
                    self._show_message(
                        "Wallet Restored", f"Wallet {record.label} restored at {record.address}."
                    )
                elif choice == "sign":
                    label = self._prompt_text("Sign Message", "Wallet label")
                    if not label:
                        continue
                    message = self._prompt_text("Sign Message", "Message to sign")
                    if message is None:
                        continue
                    signature = self.wallets.sign_message(label=label, message=message)
                    self._show_message("Signature", signature)
                elif choice == "balance":
                    label = self._prompt_text("Balance", "Wallet label")
                    if not label:
                        continue
                    payload = self.wallets.balance(label=label)
                    self._show_panel("Wallet Balance", json.dumps(payload, indent=2, ensure_ascii=False))
                elif choice == "vanity":
                    pattern = self._prompt_text("Vanity", "Hex pattern (prefix)")
                    if not pattern:
                        continue
                    case_sensitive = self._prompt_confirm(
                        "Case Sensitivity", "Should the search be case sensitive?"
                    )
                    attempts_text = self._prompt_text(
                        "Vanity", "Max attempts", default="500000"
                    )
                    attempts = int(attempts_text or "500000")
                    payload = self.wallets.generate_vanity(
                        pattern,
                        case_sensitive=case_sensitive,
                        max_attempts=attempts,
                    )
                    self._show_panel(
                        "Vanity Result", json.dumps(payload, indent=2, ensure_ascii=False)
                    )
            except Exception as exc:
                self._show_message("Wallet Error", f"{type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------
    # Safes
    # ------------------------------------------------------------------
    def _handle_safes(self) -> None:
        while True:
            choice = button_dialog(
                title="Safe Operations",
                text="Gnosis Safe management",
                buttons=[
                    ("Deploy Safe", "deploy"),
                    ("Manage Owners", "owners"),
                    ("Submit Transaction", "tx"),
                    ("Back", "back"),
                ],
            ).run()
            if choice in (None, "back"):
                return
            try:
                if choice == "deploy":
                    owners_text = self._prompt_text(
                        "Deploy Safe", "Owner addresses (comma separated)"
                    )
                    if not owners_text:
                        continue
                    owners = [item.strip() for item in owners_text.split(",") if item.strip()]
                    threshold_text = self._prompt_text(
                        "Deploy Safe", "Threshold (blank for auto)", default=""
                    )
                    threshold = int(threshold_text) if threshold_text else None
                    deployment = self.safes.deploy_safe(owners=owners, threshold=threshold)
                    self._show_panel(
                        "Safe Deployed",
                        json.dumps(
                            {"address": deployment.address, "tx_hash": deployment.tx_hash},
                            indent=2,
                            ensure_ascii=False,
                        ),
                    )
                elif choice == "owners":
                    safe_address = self._prompt_text("Manage Owners", "Safe address")
                    if not safe_address:
                        continue
                    add_owner = self._prompt_text(
                        "Manage Owners", "Owner to add (blank to skip)", default=""
                    )
                    remove_owner = self._prompt_text(
                        "Manage Owners", "Owner to remove (blank to skip)", default=""
                    )
                    threshold_text = self._prompt_text(
                        "Manage Owners", "New threshold (blank to keep)"
                    )
                    threshold = int(threshold_text) if threshold_text else None
                    tx_hash = self.safes.manage_owners(
                        safe_address=safe_address,
                        add_owner=add_owner or None,
                        remove_owner=remove_owner or None,
                        threshold=threshold,
                    )
                    self._show_message("Safe Owners", f"Transaction hash: {tx_hash}")
                elif choice == "tx":
                    safe_address = self._prompt_text("Safe Tx", "Safe address")
                    if not safe_address:
                        continue
                    to_address = self._prompt_text("Safe Tx", "Destination address")
                    if not to_address:
                        continue
                    value_text = self._prompt_text("Safe Tx", "Value (wei)", default="0")
                    value = int(value_text or "0")
                    data_hex = self._prompt_text("Safe Tx", "Data payload (hex)", default="0x") or "0x"
                    op_text = self._prompt_text("Safe Tx", "Operation (0=call,1=delegate)", default="0")
                    operation = int(op_text or "0")
                    tx_hash = self.safes.handle_transaction(
                        safe_address=safe_address,
                        to=to_address,
                        value=value,
                        data=bytes.fromhex(data_hex[2:]) if data_hex.startswith("0x") else data_hex.encode("utf-8"),
                        operation=operation,
                    )
                    self._show_message("Safe Tx", f"Transaction hash: {tx_hash}")
            except Exception as exc:
                self._show_message("Safe Error", f"{type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------
    # Contracts & ABI
    # ------------------------------------------------------------------
    def _handle_contracts(self) -> None:
        while True:
            choice = button_dialog(
                title="Contracts & ABI Lab",
                text="Inspect ABI payloads and execute read-only calls.",
                buttons=[
                    ("Load Contract", "load"),
                    ("List Stored ABIs", "list"),
                    ("Save ABI", "save"),
                    ("Simulate Call", "call"),
                    ("Back", "back"),
                ],
            ).run()
            if choice in (None, "back"):
                return
            try:
                if choice == "load":
                    path_text = self._prompt_text("Contracts", "ABI or artifact path")
                    if not path_text:
                        continue
                    name = self._prompt_text(
                        "Contracts", "Contract name (blank to infer)", default=""
                    )
                    address = self._prompt_text(
                        "Contracts", "Contract address (optional)", default=""
                    )
                    summary = self.contracts.load_contract(
                        path=path_text,
                        name=name or None,
                        address=address or None,
                    )
                    table = Table(title=f"{summary.name} functions", show_header=True)
                    table.add_column("Selector", style="cyan")
                    table.add_column("Signature", style="green")
                    for entry in summary.functions:
                        signature = f"{entry['name']}({', '.join(param['type'] for param in entry['inputs'])})"
                        table.add_row(entry["selector"], signature)
                    self._render_table("Contract Functions", table)
                elif choice == "list":
                    entries = abi_manager.list_abis()
                    table = Table(title="Stored ABI Snapshots")
                    table.add_column("Name", style="cyan")
                    if not entries:
                        self._show_message("ABI", "No ABI snapshots stored in ~/.gnoman/abis.")
                    else:
                        for item in entries:
                            table.add_row(item)
                        self._render_table("ABI", table)
                elif choice == "save":
                    path_text = self._prompt_text("Save ABI", "Path to ABI JSON")
                    if not path_text:
                        continue
                    name = self._prompt_text("Save ABI", "Snapshot name")
                    if not name:
                        continue
                    payload = abi_manager.load_abi_from_file(path_text)
                    saved_path = abi_manager.save_abi(name, {"abi": payload})
                    self._show_message("ABI", f"Stored ABI snapshot at {saved_path}")
                elif choice == "call":
                    name = self._prompt_text(
                        "Simulate Call", "ABI name (stored) or file path"
                    )
                    if not name:
                        continue
                    try:
                        abi_data = abi_manager.load_abi(name)
                    except FileNotFoundError:
                        abi_data = abi_manager.load_abi_from_file(name)
                    address = self._prompt_text("Simulate Call", "Contract address")
                    if not address:
                        continue
                    method = self._prompt_text("Simulate Call", "Method name")
                    if not method:
                        continue
                    args_text = self._prompt_text(
                        "Simulate Call", "Arguments (comma separated)", default=""
                    )
                    args = [item.strip() for item in args_text.split(",") if item.strip()]
                    rpc_url = self._prompt_text(
                        "Simulate Call", "RPC URL (blank for tester)", default=""
                    )
                    if rpc_url:
                        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
                    else:
                        w3 = Web3(EthereumTesterProvider())
                    result = abi_manager.simulate_call(w3, address, abi_data, method, args)
                    self._show_panel("Call Result", json.dumps(result, indent=2, ensure_ascii=False))
            except Exception as exc:
                self._show_message("Contract Error", f"{type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    def _handle_audit(self) -> None:
        output = self._prompt_text(
            "Audit", "Output path (blank for ~/.gnoman/audits/<timestamp>.json)", default=""
        )
        passphrase = self._prompt_text(
            "Audit", "Encrypt with passphrase (optional)", password=True
        )
        path = self.audit.run_audit(output=output or None, encrypt_passphrase=passphrase or None)
        self._show_message("Audit", f"Audit report generated at {path}")

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------
    def _handle_sync(self) -> None:
        choice = button_dialog(
            title="Sync Recon",
            text="Synchronise environment credentials",
            buttons=[
                ("Analyse", "analyse"),
                ("Reconcile", "reconcile"),
                ("Keyring Dump", "dump"),
                ("Back", "back"),
            ],
        ).run()
        if choice in (None, "back"):
            return
        if choice == "analyse":
            report = self.sync.analyse()
            self._render_sync_report(report)
        elif choice == "reconcile":
            update_env = self._prompt_confirm(
                "Sync", "Update .env.secure with keyring values?"
            )
            update_keyring = self._prompt_confirm(
                "Sync", "Update keyring with secure env values?"
            )
            report = self.sync.reconcile(update_env=update_env, update_keyring=update_keyring)
            self._render_sync_report(report)
        elif choice == "dump":
            entries = [
                {
                    "service": entry.service,
                    "username": entry.username,
                    "metadata": entry.metadata,
                }
                for entry in keyring_backend.list_all_entries()
            ]
            self._show_panel("Keyring Entries", json.dumps(entries, indent=2, ensure_ascii=False))


def launch_terminal() -> None:
    """Convenience wrapper for launching :class:`TerminalUI`."""

    TerminalUI().run()


__all__ = ["TerminalUI", "launch_terminal"]
