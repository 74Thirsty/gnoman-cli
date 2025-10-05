"""Application entry point launching the GNOMAN dashboard."""

from __future__ import annotations

from . import __version__
from .audit import append_record
from .ui.main import GNOMANMain


def main() -> None:
    """Start the interactive Textual dashboard."""

    try:
        append_record("ui.start", {"version": __version__}, True, {"mode": "dashboard"})
    except (NotImplementedError, ValueError):
        # Audit signing is optional but encouraged.
        pass
    GNOMANMain().run()


__all__ = ["main"]

