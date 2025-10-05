"""Tests for the audit log chaining and signatures."""

from __future__ import annotations

import base64
import hashlib
import importlib
import json
import os
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519


@pytest.fixture()
def logbook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GNOMAN_STATE_DIR", str(tmp_path))
    module_name = "gnoman.utils.logbook"
    if module_name in sys.modules:
        del sys.modules[module_name]
    module = importlib.import_module(module_name)
    yield module
    if module_name in sys.modules:
        del sys.modules[module_name]


def _verify_entry(entry: dict) -> None:
    public_key = ed25519.Ed25519PublicKey.from_public_bytes(
        base64.b64decode(entry["public_key"])
    )
    base_entry = {k: entry[k] for k in ("ts", "prev", "record")}
    canonical = json.dumps(base_entry, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical).digest()
    public_key.verify(base64.b64decode(entry["signature"]), digest)
    assert entry["hash"] == hashlib.sha256(canonical).hexdigest()


def test_audit_log_chain(logbook, tmp_path: Path) -> None:
    logbook.info({"action": "unit", "value": 1})
    logbook.info({"action": "unit", "value": 2})

    audit_path = Path(os.environ["GNOMAN_STATE_DIR"]) / "audit.jsonl"
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    second = json.loads(lines[1])

    assert first["prev"] is None
    assert second["prev"] == first["hash"]

    _verify_entry(first)
    _verify_entry(second)
