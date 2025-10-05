"""Curses dashboard launcher placeholder."""

from __future__ import annotations

from ..core.log_manager import log_event


def launch_dashboard() -> None:
    """Entry point for the terminal dashboard."""

    log_event("dashboard-launch", status="pending")
    raise NotImplementedError("Dashboard UI has not been implemented yet")


__all__ = ["launch_dashboard"]
