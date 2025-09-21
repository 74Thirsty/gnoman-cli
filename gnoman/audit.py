"""Forensic audit report generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .core import AppContext, get_context
from .safe import SafeManager
from .sync import SecretSyncer
from .wallet import WalletService

AUDIT_DIR = Path.home() / ".gnoman" / "audits"


@dataclass
class AuditReport:
    payload: Dict[str, object]
    signature: str
    json_path: Path
    pdf_path: Path


class AuditService:
    """Aggregate Safe, wallet, and secret state into forensic reports."""

    def __init__(self, context: Optional[AppContext] = None) -> None:
        self.context = context or get_context()
        self.safe = SafeManager(self.context)
        self.syncer = SecretSyncer(self.context)
        self.wallet_service = WalletService(self.context)

    # -- collection -------------------------------------------------------
    def collect(self) -> Dict[str, object]:
        safe_info = self.safe.info()
        wallets = self.wallet_service.list_accounts()
        secrets = self.syncer.list_status()
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "safe": safe_info,
            "wallets": wallets,
            "secrets": secrets,
        }
        self.context.ledger.log(
            "audit_collect",
            result={"wallets": len(wallets), "secrets": len(secrets)},
        )
        return payload

    # -- signing ----------------------------------------------------------
    def sign(self, payload: Dict[str, object]) -> str:
        serialised = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = self.context.ledger.log(
            "audit_sign",
            params={"size": len(serialised)},
            result={},
        )["hash"]
        return signature

    # -- persistence ------------------------------------------------------
    def generate(self) -> AuditReport:
        payload = self.collect()
        signature = self.sign(payload)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        json_path = AUDIT_DIR / f"audit-{timestamp}.json"
        pdf_path = AUDIT_DIR / f"audit-{timestamp}.pdf"

        report = {"payload": payload, "signature": signature}
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        pdf_path.write_bytes(self._build_pdf(payload, signature, timestamp))

        self.context.ledger.log(
            "audit_write",
            result={"json": str(json_path), "pdf": str(pdf_path)},
        )
        return AuditReport(payload=payload, signature=signature, json_path=json_path, pdf_path=pdf_path)

    # -- helpers ----------------------------------------------------------
    def _build_pdf(self, payload: Dict[str, object], signature: str, timestamp: str) -> bytes:
        lines: List[str] = [
            f"GNOMAN Forensic Audit — {timestamp}Z",
            "",
            "Safe:",
        ]
        safe = payload.get("safe", {})
        if isinstance(safe, dict):
            owners = ", ".join(safe.get("owners", []))
            lines.append(f"  {safe.get('safe')} threshold={safe.get('threshold')} owners=[{owners}]")
            lines.append(f"  balance={safe.get('balance_eth')} ETH nonce={safe.get('nonce')}")
        lines.append("")
        lines.append("Wallets:")
        for wallet in payload.get("wallets", []):
            lines.append(
                f"  {wallet.get('label', 'wallet')} {wallet.get('address')} — path {wallet.get('derivation_path')}"
            )
        lines.append("")
        lines.append("Secrets:")
        for secret in payload.get("secrets", []):
            lines.append(
                f"  {secret.get('key')} status={secret.get('status')} sources={secret.get('sources')}"
            )
        lines.append("")
        lines.append(f"Signature: {signature}")

        return self._encode_pdf(lines)

    def _encode_pdf(self, lines: List[str]) -> bytes:
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
        offsets = [0] + offsets

        xref_offset = sum(len(part) for part in encoded_parts)
        xref_lines = ["xref\n", "0 6\n", "0000000000 65535 f \n"]
        for off in offsets[1:]:
            xref_lines.append(f"{off:010d} 00000 n \n")
        xref = "".join(xref_lines)
        trailer = "trailer<< /Size 6 /Root 1 0 R >>\n"
        startxref = f"startxref\n{xref_offset}\n%%EOF\n"

        return b"".join(encoded_parts + [xref.encode("utf-8"), trailer.encode("utf-8"), startxref.encode("utf-8")])


def load_service(context: Optional[AppContext] = None) -> AuditService:
    return AuditService(context=context)
