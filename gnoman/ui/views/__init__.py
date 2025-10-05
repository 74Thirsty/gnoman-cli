"""View registry for the dashboard."""

from .abi_view import ABIScreen
from .audit_view import View as AuditView
from .safes_view import View as SafesView
from .secrets_view import View as SecretsView
from .sync_view import View as SyncView
from .wallets_view import View as WalletsView

__all__ = [
    "ABIScreen",
    "AuditView",
    "SafesView",
    "SecretsView",
    "SyncView",
    "WalletsView",
]
