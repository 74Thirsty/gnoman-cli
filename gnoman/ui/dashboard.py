"""Compatibility shim for launching the Textual dashboard."""

from __future__ import annotations

from ..core.log_manager import log_event
from .main import GNOMANMain


def launch_dashboard() -> None:
    """Entry point for the terminal dashboard."""

    log_event("dashboard-launch", status="started")
    GNOMANMain().run()


__all__ = ["launch_dashboard"]
