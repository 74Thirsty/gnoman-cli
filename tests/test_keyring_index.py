"""Unit tests for the keyring index helpers."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from gnoman.utils import keyring_index


class DummyKeyring:
    def __init__(self) -> None:
        self._data: Dict[Tuple[str, str], str] = {}

    def get_password(self, service: str, key: str) -> Optional[str]:
        return self._data.get((service, key))

    def set_password(self, service: str, key: str, value: str) -> None:
        self._data[(service, key)] = value

    def delete_password(self, service: str, key: str) -> None:
        self._data.pop((service, key), None)


def test_register_and_list_keys() -> None:
    backend = DummyKeyring()
    service = "gnoman-test"

    backend.set_password(service, "ALPHA", "secret")
    keyring_index.register_key(backend, service, "ALPHA")
    backend.set_password(service, "BETA", "value")
    keyring_index.register_key(backend, service, "BETA")

    keys = keyring_index.list_keys(backend, service)
    assert keys == ["ALPHA", "BETA"]


def test_unregister_keys_and_clear_index() -> None:
    backend = DummyKeyring()
    service = "gnoman-test"

    backend.set_password(service, "ALPHA", "secret")
    backend.set_password(service, "BETA", "value")
    keyring_index.register_key(backend, service, "ALPHA")
    keyring_index.register_key(backend, service, "BETA")

    keyring_index.unregister_key(backend, service, "ALPHA")
    assert keyring_index.list_keys(backend, service) == ["BETA"]

    keyring_index.unregister_key(backend, service, "BETA")
    assert keyring_index.list_keys(backend, service) == []
    assert backend.get_password(service, keyring_index.INDEX_KEY) is None
