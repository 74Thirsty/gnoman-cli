"""Secure master seed handling backed by the keyring service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

try:  # pragma: no cover - depends on runtime environment
    import keyring  # type: ignore
except Exception:  # pragma: no cover - if keyring is unavailable
    keyring = None  # type: ignore


class KeyringLike(Protocol):
    """Protocol describing the subset of keyring used by the wallet."""

    def get_password(self, service: str, key: str) -> Optional[str]:
        ...

    def set_password(self, service: str, key: str, value: str) -> None:
        ...

    def delete_password(self, service: str, key: str) -> None:
        ...


class WalletSeedError(RuntimeError):
    """Base exception for seed storage failures."""


class SeedNotFoundError(WalletSeedError):
    """Raised when no seed material could be located."""


@dataclass
class WalletSeedManager:
    """Encapsulate secure retrieval and storage of wallet seed material.

    The manager never emits the seed in logs and relies on the configured
    keyring backend for persistence. For tests a custom backend implementing
    :class:`KeyringLike` can be injected.
    """

    service_name: str = "gnoman"
    backend: Optional[KeyringLike] = None

    MNEMONIC_KEY = "WALLET_MASTER_MNEMONIC"
    ENTROPY_KEY = "WALLET_MASTER_ENTROPY"
    PASSPHRASE_KEY = "WALLET_PASSPHRASE"

    def __post_init__(self) -> None:
        if self.backend is None:
            if keyring is None:
                raise WalletSeedError("keyring backend is not available")
            self.backend = keyring  # type: ignore[assignment]

    # -- internal helpers -------------------------------------------------
    def _get(self, key: str) -> Optional[str]:
        assert self.backend is not None
        try:
            return self.backend.get_password(self.service_name, key)
        except Exception as exc:  # pragma: no cover - backend specific
            raise WalletSeedError(f"failed to read {key!r} from keyring") from exc

    def _set(self, key: str, value: str) -> None:
        assert self.backend is not None
        try:
            self.backend.set_password(self.service_name, key, value)
        except Exception as exc:  # pragma: no cover - backend specific
            raise WalletSeedError(f"failed to store {key!r} in keyring") from exc

    def _delete(self, key: str) -> None:
        assert self.backend is not None
        try:
            self.backend.delete_password(self.service_name, key)
        except Exception:  # pragma: no cover - deletion failures are non fatal
            return

    # -- mnemonic / entropy management ------------------------------------
    def store_mnemonic(self, mnemonic: str) -> None:
        if not mnemonic.strip():
            raise WalletSeedError("mnemonic must not be empty")
        self._set(self.MNEMONIC_KEY, mnemonic.strip())

    def get_mnemonic(self) -> str:
        mnemonic = self._get(self.MNEMONIC_KEY)
        if mnemonic:
            return mnemonic
        raise SeedNotFoundError("wallet mnemonic not found in keyring")

    def clear_mnemonic(self) -> None:
        self._delete(self.MNEMONIC_KEY)

    def store_entropy(self, entropy_hex: str) -> None:
        if not entropy_hex.strip():
            raise WalletSeedError("entropy must not be empty")
        self._set(self.ENTROPY_KEY, entropy_hex.strip())

    def get_entropy(self) -> str:
        entropy = self._get(self.ENTROPY_KEY)
        if entropy:
            return entropy
        raise SeedNotFoundError("wallet entropy not found in keyring")

    def clear_entropy(self) -> None:
        self._delete(self.ENTROPY_KEY)

    def store_passphrase(self, passphrase: str) -> None:
        self._set(self.PASSPHRASE_KEY, passphrase)

    def get_passphrase(self) -> str:
        value = self._get(self.PASSPHRASE_KEY)
        return value or ""

    def clear_passphrase(self) -> None:
        self._delete(self.PASSPHRASE_KEY)

    # -- metadata helpers --------------------------------------------------
    def store_metadata(self, key: str, value: str) -> None:
        self._set(key, value)

    def get_metadata(self, key: str) -> Optional[str]:
        return self._get(key)
