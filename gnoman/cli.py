"""Compatibility shim delegating to the interactive dashboard."""

from __future__ import annotations

from typing import Any, Optional, Sequence

from .app import main as app_main


def main(argv: Optional[Sequence[str]] = None) -> Any:
    """Entry point retained for backwards compatibility."""

    return app_main(argv)