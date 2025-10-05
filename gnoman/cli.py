"""Command line interface for the GNOMAN mission-control console."""

from __future__ import annotations

import getpass
from typing import Iterable, Optional, Sequence

import click

from . import __version__
from .core.audit_manager import AuditManager
from .core.contract_manager import ContractManager
from .core.log_manager import log_event
from .core.safe_manager import SafeManager
from .core.secrets_manager import SecretRecord, SecretsManager
from .core.sync_manager import SyncManager
from .core.wallet_manager import WalletManager
from .ui.dashboard import launch_dashboard


def _comma_separated(value: Optional[str]) -> Optional[Iterable[str]]:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _handle_operation(action: str, func) -> None:
    try:
        func()
    except NotImplementedError as exc:  # pragma: no cover - signalling to user
        raise click.ClickException(f"{action} is not implemented: {exc}") from exc


def _format_secret(record: SecretRecord, include_values: bool) -> str:
    base = f"{record.service}/{record.username or '<no-username>'}"
    metadata = []
    if record.metadata:
        for key in sorted(record.metadata):
            metadata.append(f"{key}={record.metadata[key]}")
    suffix = f" [{' '.join(metadata)}]" if metadata else ""
    if include_values and record.secret is not None:
        return f"{base}{suffix}: {record.secret}"
    return f"{base}{suffix}"


@click.group(name="gnoman")
@click.version_option(version=__version__, prog_name="gnoman")
def cli() -> None:
    """GNOMAN mission-control console for wallets and multisig operations."""


@cli.group()
def secrets() -> None:
    """Manage secrets stored in the operating system keyring."""


@secrets.command("list")
@click.option("--namespace", help="Restrict results to services starting with the prefix")
@click.option("--show-values", is_flag=True, help="Display secret values alongside identifiers")
def secrets_list(namespace: Optional[str], show_values: bool) -> None:
    manager = SecretsManager()
    records = manager.list(namespace=namespace, include_values=show_values)
    if not records:
        click.echo("No secrets found")
        return
    for record in records:
        click.echo(_format_secret(record, include_values=show_values))


@secrets.command("add")
@click.argument("service")
@click.argument("username")
@click.option("--secret", help="Secret value to store; prompted when omitted", default=None)
def secrets_add(service: str, username: str, secret: Optional[str]) -> None:
    manager = SecretsManager()
    value = secret or click.prompt("Secret", hide_input=True, confirmation_prompt=True)
    manager.add(service=service, username=username, secret=value)
    click.echo(f"Stored secret for {service}/{username}")


@secrets.command("delete")
@click.argument("service")
@click.argument("username")
@click.option("--force", is_flag=True, help="Skip the confirmation prompt")
def secrets_delete(service: str, username: str, force: bool) -> None:
    if not force and not click.confirm(f"Delete secret {service}/{username}?", default=False):
        raise click.Abort()
    manager = SecretsManager()
    manager.delete(service=service, username=username)
    click.echo(f"Deleted secret for {service}/{username}")


@secrets.command("rotate")
@click.option("--services", help="Comma separated service allow list", default=None)
@click.option("--length", type=int, default=32, show_default=True, help="Generated secret length")
def secrets_rotate(services: Optional[str], length: int) -> None:
    manager = SecretsManager()
    rotated = manager.rotate(services=_comma_separated(services), length=length)
    click.echo(f"Rotated {rotated} secret(s)")


@cli.command("sync")
def sync_command() -> None:
    manager = SyncManager()
    _handle_operation("Secret synchronisation", lambda: manager.sync())


@cli.group()
def wallet() -> None:
    """HD wallet lifecycle operations."""


@wallet.command("new")
@click.option("--path", help="Derivation path to use when creating the wallet")
def wallet_new(path: Optional[str]) -> None:
    manager = WalletManager()
    _handle_operation("Wallet creation", lambda: manager.create_wallet(path=path))


@wallet.command("import")
@click.option("--mnemonic", help="Seed phrase to import")
@click.option("--private-key", help="Raw private key in hex format")
def wallet_import(mnemonic: Optional[str], private_key: Optional[str]) -> None:
    manager = WalletManager()
    _handle_operation(
        "Wallet import",
        lambda: manager.import_wallet(mnemonic=mnemonic, private_key=private_key),
    )


@wallet.command("show")
@click.argument("address")
@click.option("--network", default="mainnet", help="Ethereum network name")
def wallet_show(address: str, network: str) -> None:
    manager = WalletManager()
    _handle_operation(
        "Wallet inspection",
        lambda: manager.show_wallet(address=address, network=network),
    )


@cli.group()
def safe() -> None:
    """Gnosis Safe orchestration commands."""


@safe.command("deploy")
@click.option("--owners", help="Comma separated owner addresses")
@click.option("--threshold", type=int, help="Required approval threshold")
@click.option("--network", default="mainnet", help="Ethereum network name")
def safe_deploy(owners: Optional[str], threshold: Optional[int], network: str) -> None:
    manager = SafeManager()
    _handle_operation(
        "Safe deployment",
        lambda: manager.deploy_safe(
            owners=list(_comma_separated(owners) or []),
            threshold=threshold,
            network=network,
        ),
    )


@safe.command("owners")
@click.argument("safe_address")
@click.option("--add", help="Owner address to add")
@click.option("--remove", help="Owner address to remove")
@click.option("--network", default="mainnet", help="Ethereum network name")
def safe_owners(safe_address: str, add: Optional[str], remove: Optional[str], network: str) -> None:
    manager = SafeManager()
    _handle_operation(
        "Safe owner management",
        lambda: manager.manage_owners(
            safe_address=safe_address,
            add_owner=add,
            remove_owner=remove,
            network=network,
        ),
    )


@safe.command("tx")
@click.argument("safe_address")
@click.option("--action", type=click.Choice(["build", "sign", "execute", "simulate"]))
@click.option("--payload", help="Transaction payload (JSON)")
@click.option("--network", default="mainnet", help="Ethereum network name")
def safe_tx(safe_address: str, action: Optional[str], payload: Optional[str], network: str) -> None:
    manager = SafeManager()
    _handle_operation(
        "Safe transaction processing",
        lambda: manager.handle_transaction(
            safe_address=safe_address,
            action=action,
            payload=payload,
            network=network,
        ),
    )


@cli.group()
def contract() -> None:
    """Contract ABI management commands."""


@contract.command("load")
@click.argument("path")
@click.option("--name", help="Symbolic name for the contract")
def contract_load(path: str, name: Optional[str]) -> None:
    manager = ContractManager()
    _handle_operation(
        "Contract loading",
        lambda: manager.load_contract(path=path, name=name),
    )


@cli.group()
def audit() -> None:
    """Forensic audit tooling."""


@audit.command("run")
@click.option("--output", help="Destination file for the report")
def audit_run(output: Optional[str]) -> None:
    manager = AuditManager()
    _handle_operation("Audit execution", lambda: manager.run_audit(output=output))


@cli.command("dashboard")
def dashboard() -> None:
    _handle_operation("Dashboard launch", launch_dashboard)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point compatible with :mod:`python -m gnoman`."""

    cli.main(standalone_mode=True, prog_name="gnoman", args=argv)
    log_event("cli-exit", user=getpass.getuser(), argv=list(argv or []))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()
