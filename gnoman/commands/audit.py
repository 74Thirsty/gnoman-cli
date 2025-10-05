"""Forensic audit command implementation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from ..services import get_audit_reporter, get_audit_signer
from ..utils import logbook

AUDIT_DIR = Path.home() / ".gnoman" / "audits"


def run(args) -> Dict[str, object]:
    collector = get_audit_reporter()
    signer = get_audit_signer()

    payload = collector.collect()
    signature = signer.sign(payload)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = AUDIT_DIR / f"audit-{timestamp}.json"
    pdf_path = AUDIT_DIR / f"audit-{timestamp}.pdf"

    report = {"payload": payload, "signature": signature}
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_pdf(pdf_path, payload, signature, timestamp)

    record = {
        "action": "audit_snapshot",
        "status": "generated",
        "json_path": str(json_path),
        "pdf_path": str(pdf_path),
        "signature": signature,
    }
    logbook.info(record)
    print(f"[AUDIT] Report written to {json_path}")
    print(f"[AUDIT] Signed PDF stored at {pdf_path}")
    return record


def _write_pdf(path: Path, payload: Dict[str, object], signature: str, timestamp: str) -> None:
    lines: List[str] = [
        f"GNOMAN Forensic Audit — {timestamp}Z",
        "", "Wallets:",
    ]
    for wallet in payload.get("wallets", []):
        lines.append(
            f"  {wallet['name']} {wallet['address']} — balance {wallet['balance']} ETH"
        )
    lines.append("")
    lines.append("Safes:")
    for safe in payload.get("safes", []):
        owners = ", ".join(safe.get("owners", []))
        lines.append(
            f"  {safe['address']} threshold={safe.get('threshold')} owners=[{owners}]"
        )
    lines.append("")
    lines.append("Expiring secrets:")
    for secret in payload.get("expiring_secrets", []):
        lines.append(
            f"  {secret['key']} expires in {secret['expires_in_days']} days"
        )
    lines.append("")
    lines.append(f"Signature: {signature}")

    pdf_bytes = _build_pdf(lines)
    path.write_bytes(pdf_bytes)


def _build_pdf(lines: List[str]) -> bytes:
    def esc(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    header = "%PDF-1.4\n"
    obj1 = "1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
    obj2 = "2 0 obj<< /Type /Pages /Count 1 /Kids[3 0 R] >>endobj\n"
    obj3 = (
        "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox[0 0 612 792] "
        "/Resources<< /Font<< /F1 5 0 R >> >> /Contents 4 0 R >>endobj\n"
    )
    cursor_y = 760
    content_segments: List[str] = []
    for line in lines:
        content_segments.append(f"BT /F1 12 Tf 72 {cursor_y} Td ({esc(line)}) Tj ET\n")
        cursor_y -= 16
    stream = "".join(content_segments)
    stream_bytes = stream.encode("utf-8")
    obj4 = f"4 0 obj<< /Length {len(stream_bytes)} >>stream\n{stream}endstream\nendobj\n"
    obj5 = "5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n"

    parts = [header, obj1, obj2, obj3, obj4, obj5]
    encoded_parts = [part.encode("utf-8") for part in parts]

    offsets: List[int] = []
    position = len(encoded_parts[0])
    for part in encoded_parts[1:]:
        offsets.append(position)
        position += len(part)
    offsets = [0] + offsets  # object 0 placeholder

    xref_offset = sum(len(part) for part in encoded_parts)
    xref_lines = ["xref\n", "0 6\n", "0000000000 65535 f \n"]
    for off in offsets[1:]:
        xref_lines.append(f"{off:010d} 00000 n \n")
    xref = "".join(xref_lines)
    trailer = "trailer<< /Size 6 /Root 1 0 R >>\n"
    startxref = f"startxref\n{xref_offset}\n%%EOF\n"

    return b"".join(encoded_parts + [xref.encode("utf-8"), trailer.encode("utf-8"), startxref.encode("utf-8")])
