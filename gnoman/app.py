"""Application entry point launching the GNOMAN dashboard."""

from __future__ import annotations

import importlib.util
import sys
from textwrap import dedent

from . import __version__
from .audit import append_record


def _missing_dashboard_dependencies() -> list[str]:
    """Return a list of importable package names required for the dashboard.

    GNOMAN bundles a Textual-based interface that depends on third-party
    packages. When GNOMAN is executed from a source checkout without the
    project being installed, those dependencies may be absent. Instead of
    failing with a low-level ``ModuleNotFoundError`` we proactively probe for
    the imports we need and surface a user-friendly diagnostic.
    """

    required = ("textual", "rich")
    return [name for name in required if importlib.util.find_spec(name) is None]


def _print_dependency_error(missing: list[str]) -> None:
    """Emit guidance for installing runtime dependencies."""

    message = dedent(
        f"""
        GNOMAN could not start because the following Python packages are missing:
            {', '.join(sorted(missing))}

        Install the project dependencies before launching the dashboard, e.g.:
            python -m pip install -e .
        or install the published package:
            python -m pip install gnoman-cli
        """
    ).strip()
    print(message, file=sys.stderr)


def main() -> None:
    """Start the interactive Textual dashboard."""

    missing = _missing_dashboard_dependencies()
    if missing:
        _print_dependency_error(missing)
        raise SystemExit(1)

    from .ui.main import GNOMANMain

    try:
        append_record("ui.start", {"version": __version__}, True, {"mode": "dashboard"})
    except (NotImplementedError, ValueError):
        # Audit signing is optional but encouraged.
        pass
    GNOMANMain().run()


__all__ = ["main"]

