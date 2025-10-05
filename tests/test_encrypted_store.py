"""Tests for the AES-GCM encrypted JSON store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gnoman.security import EncryptedJSONStore, EncryptedStoreError


@pytest.fixture()
def tmp_store(tmp_path: Path) -> Path:
    return tmp_path / "wallet.enc"


def test_roundtrip(tmp_store: Path) -> None:
    store = EncryptedJSONStore(path=tmp_store, passphrase_resolver=lambda: "hunter2")
    payload = {"alpha": 1, "beta": [2, 3, 4]}
    store.save(payload)
    restored = store.load({})
    assert restored == payload
    # ensure file is encrypted
    on_disk = json.loads(tmp_store.read_text(encoding="utf-8"))
    assert "ciphertext" in on_disk
    assert on_disk["ciphertext"] != ""  # ciphertext never empty


def test_invalid_passphrase_rejected(tmp_store: Path) -> None:
    store = EncryptedJSONStore(path=tmp_store, passphrase_resolver=lambda: "correct")
    store.save({"secret": "value"})
    wrong = EncryptedJSONStore(path=tmp_store, passphrase_resolver=lambda: "wrong")
    with pytest.raises(EncryptedStoreError):
        wrong.load({})


def test_rotate_passphrase(tmp_store: Path) -> None:
    resolver = ["old"]

    def _resolver() -> str:
        return resolver[0]

    store = EncryptedJSONStore(path=tmp_store, passphrase_resolver=_resolver)
    store.save({"payload": 7})
    store.rotate_passphrase("new-passphrase")
    resolver[0] = "new-passphrase"
    restored = store.load({})
    assert restored == {"payload": 7}
