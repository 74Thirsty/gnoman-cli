"""Graph export utilities."""

from __future__ import annotations

import json
import struct
import time
import zlib
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .core import AppContext, get_context
from .plugin import PluginRegistry
from .safe import SafeManager
from .wallet import WalletService

GRAPH_DIR = Path.home() / ".gnoman" / "graphs"


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)


class GraphManager:
    """Produce Safe/network topology exports for operators."""

    def __init__(self, context: Optional[AppContext] = None, *, output_dir: Path = GRAPH_DIR) -> None:
        self.context = context or get_context()
        self.safe = SafeManager(self.context)
        self.wallet = WalletService(self.context)
        self.plugins = PluginRegistry(self.context)
        self.output_dir = output_dir
        _ensure_directory(self.output_dir)

    # -- data -------------------------------------------------------------
    def _graph_data(self) -> Dict[str, object]:
        safe_info = self.safe.info()
        wallets = self.wallet.list_accounts()
        plugin_versions = self.plugins.list_plugins()
        return {
            "safe": {
                "address": safe_info.get("address"),
                "owners": safe_info.get("owners", []),
                "threshold": safe_info.get("threshold"),
                "guard": safe_info.get("guard"),
            },
            "wallets": wallets,
            "plugins": plugin_versions,
            "generated_at": time.time(),
        }

    # -- writers ----------------------------------------------------------
    def _target_path(self, fmt: str, output: Optional[Path]) -> Path:
        if output is None:
            timestamp = int(time.time())
            return self.output_dir / f"graph_{timestamp}.{fmt}"
        output = Path(output)
        if output.is_dir():
            timestamp = int(time.time())
            return output / f"graph_{timestamp}.{fmt}"
        _ensure_directory(output.parent)
        return output

    def _write_svg(self, path: Path, data: Dict[str, object], highlight: Iterable[str]) -> None:
        owners = data["safe"].get("owners", []) if isinstance(data["safe"], dict) else []
        highlight_text = ",".join(highlight)
        svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='480' height='320'>
  <style>text {{ font-family: monospace; font-size: 12px; }}</style>
  <rect x='0' y='0' width='480' height='320' fill='#0b253a' />
  <text x='16' y='32' fill='#7dd3fc'>Safe: {data['safe'].get('address')}</text>
  <text x='16' y='56' fill='#fef3c7'>Threshold: {data['safe'].get('threshold')} Guard: {data['safe'].get('guard')}</text>
  <text x='16' y='96' fill='#c7d2fe'>Owners:</text>
  {''.join(f"<text x='36' y='{120 + 18 * idx}' fill='#cbd5f5'>{owner}</text>" for idx, owner in enumerate(owners))}
  <text x='16' y='200' fill='#bbf7d0'>Plugins: {', '.join(plugin['name'] for plugin in data.get('plugins', []))}</text>
  <text x='16' y='224' fill='#fbcfe8'>Highlight: {highlight_text or 'n/a'}</text>
</svg>"""
        path.write_text(svg, encoding="utf-8")

    def _write_html(self, path: Path, data: Dict[str, object], highlight: Iterable[str]) -> None:
        html = """<html><head><meta charset='utf-8'><title>GNOMAN Graph</title>
<style>body { font-family: monospace; background: #0f172a; color: #e2e8f0; padding: 1.5rem; }
pre { background: #1e293b; padding: 1rem; border-radius: 0.5rem; }
</style></head><body>"""
        html += "<h1>GNOMAN Graph Snapshot</h1>"
        html += f"<p>Highlight: {', '.join(highlight) or 'n/a'}</p>"
        html += "<pre>" + json.dumps(data, indent=2) + "</pre>"
        html += "</body></html>"
        path.write_text(html, encoding="utf-8")

    def _write_png(self, path: Path, data: Dict[str, object], highlight: Iterable[str]) -> None:
        text = json.dumps({"highlight": list(highlight), "safe": data.get("safe", {})})
        width, height = 1, 1
        header = b"\x89PNG\r\n\x1a\n"
        ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        raw = b"\x00\xff\xff\xff\xff"
        idat = _png_chunk(b"IDAT", zlib.compress(raw))
        text_chunk = _png_chunk(b"tEXt", b"gnoman=" + text.encode("utf-8"))
        iend = _png_chunk(b"IEND", b"")
        path.write_bytes(header + ihdr + text_chunk + idat + iend)

    # -- public API -------------------------------------------------------
    def render(self, fmt: str, output: Optional[Path] = None, highlight: Optional[List[str]] = None) -> Dict[str, object]:
        fmt = fmt.lower()
        if fmt not in {"svg", "html", "png"}:
            raise ValueError("format must be svg, html, or png")
        data = self._graph_data()
        highlight_items: List[str] = list(highlight or [])
        path = self._target_path(fmt, output)
        if fmt == "svg":
            self._write_svg(path, data, highlight_items)
        elif fmt == "html":
            self._write_html(path, data, highlight_items)
        else:
            self._write_png(path, data, highlight_items)
        record = {"format": fmt, "path": str(path), "highlighted": highlight_items}
        self.context.ledger.log("graph_render", params={"format": fmt}, result=record)
        return record


def load_manager(context: Optional[AppContext] = None) -> GraphManager:
    return GraphManager(context=context)
