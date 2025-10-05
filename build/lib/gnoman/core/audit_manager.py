"""Forensic audit orchestration."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:  # pragma: no cover - optional dependency
    import pdfkit
except Exception:  # pragma: no cover
    pdfkit = None  # type: ignore[assignment]

from ..audit import read_tail_records
from ..utils import keyring_backend
from ..utils.crypto_tools import encrypt_with_passphrase, sign_payload
from ..utils.env_tools import get_gnoman_home
from .log_manager import log_event


class AuditManager:
    """Generate signed audit reports across GNOMAN subsystems."""

    def __init__(self, *, base_path: Optional[Path] = None) -> None:
        self._base_path = base_path or get_gnoman_home()
        self._reports_dir = self._base_path / "audits"
        self._reports_dir.mkdir(parents=True, exist_ok=True)

    def _build_report(self) -> dict[str, object]:
        timestamp = datetime.now(timezone.utc)
        keyring_summary = keyring_backend.audit_entries()
        tail = read_tail_records(50)
        payload = {
            "timestamp": timestamp.isoformat(),
            "keyring": keyring_summary,
            "audit_tail": tail,
        }
        payload["signature"] = sign_payload(payload)
        return payload

    def _write_pdf(self, json_path: Path, payload: dict[str, object]) -> Optional[Path]:
        if pdfkit is None:  # pragma: no cover - depends on external binary
            return None
        html_lines = ["<h1>GNOMAN Forensic Audit</h1>"]
        html_lines.append(f"<p><strong>Generated:</strong> {payload['timestamp']}</p>")
        keyring = payload.get("keyring", {})
        html_lines.append("<h2>Keyring Summary</h2>")
        html_lines.append(f"<pre>{json.dumps(keyring, indent=2, ensure_ascii=False)}</pre>")
        html_lines.append("<h2>Recent Events</h2>")
        html_lines.append(f"<pre>{json.dumps(payload.get('audit_tail', []), indent=2, ensure_ascii=False)}</pre>")
        html_lines.append(f"<p><strong>Signature:</strong> {payload['signature']}</p>")
        html = "\n".join(html_lines)
        pdf_path = json_path.with_suffix(".pdf")
        try:
            pdfkit.from_string(html, str(pdf_path))
        except Exception:  # pragma: no cover - pdfkit requires wkhtmltopdf
            return None
        return pdf_path

    def run_audit(self, *, output: Optional[str] = None, encrypt_passphrase: Optional[str] = None) -> Path:
        """Generate a signed audit snapshot."""

        report = self._build_report()
        if output:
            path = Path(output)
        else:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            path = self._reports_dir / f"audit-{timestamp}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if encrypt_passphrase:
            encrypted = encrypt_with_passphrase(report, encrypt_passphrase)
            path.write_text(json.dumps(encrypted, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        pdf_path = self._write_pdf(path, report)
        log_event(
            "audit.run",
            output=str(path),
            encrypted=bool(encrypt_passphrase),
            pdf=str(pdf_path) if pdf_path else None,
            total=report["keyring"].get("total") if isinstance(report.get("keyring"), dict) else None,
        )
        return path


__all__ = ["AuditManager"]

