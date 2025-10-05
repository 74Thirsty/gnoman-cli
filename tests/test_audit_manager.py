from __future__ import annotations

import json
from pathlib import Path

from gnoman.core.audit_manager import AuditManager
from gnoman.utils import keyring_backend


def test_audit_report_generation(isolated_home: Path, audit_key_env: str, tmp_path: Path) -> None:
    manager = AuditManager()
    keyring_backend.set_entry("gnoman.env", "API_TOKEN", "value")
    output = tmp_path / "audit.json"
    path = manager.run_audit(output=str(output))
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assert "signature" in data
    assert data["keyring"]["total"] >= 1
