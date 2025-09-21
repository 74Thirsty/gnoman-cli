from __future__ import annotations

from pathlib import Path

from gnoman.utils import keyring_compat


def test_file_keyring_roundtrip(tmp_path: Path) -> None:
    storage = tmp_path / "store.json"
    backend = keyring_compat.FileKeyring(storage_path=storage)

    assert backend.get_password("service", "alpha") is None

    backend.set_password("service", "alpha", "secret")
    assert backend.get_password("service", "alpha") == "secret"

    # Ensure persistence across instances
    another = keyring_compat.FileKeyring(storage_path=storage)
    assert another.get_password("service", "alpha") == "secret"

    another.delete_password("service", "alpha")
    assert another.get_password("service", "alpha") is None

    # No entries remain, so a new instance should see nothing either
    fresh = keyring_compat.FileKeyring(storage_path=storage)
    assert fresh.get_password("service", "alpha") is None


def test_load_keyring_backend_falls_back(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(keyring_compat, "_try_native_keyring", lambda: None)

    backend = keyring_compat.load_keyring_backend(storage_path=tmp_path / "fallback.json")
    assert backend is not None

    backend.set_password("svc", "key", "value")
    assert backend.get_password("svc", "key") == "value"
    backend.delete_password("svc", "key")
    assert backend.get_password("svc", "key") is None
