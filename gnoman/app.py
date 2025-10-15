"""Application entry point launching the GNOMAN interfaces."""

from __future__ import annotations

import argparse
import importlib.util
import logging
import sys
from textwrap import dedent
from typing import Optional, Sequence

from rich.console import Console

from . import __version__
from .audit import append_record


_BANNER = r"""
 ██████╗ ███╗   ██╗ ██████ ███╗   ███╗ █████╗ ███╗   ██╗
██╔════╝ ████╗  ██║██╔═══██╗████╗ ████║██╔══██╗████╗  ██║
██║  ███╗██╔██╗ ██║██║   ██║██╔████╔██║███████║██╔██╗ ██║
██║   ██║██║╚██╗██║██║   ██║██║╚██╔╝██║██╔══██║██║╚██╗██║
╚██████╔╝██║ ╚████║╚██████╔╝██║ ╚═╝ ██║██║  ██║██║ ╚████║
 ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝
"""


def _missing_ui_dependencies() -> list[str]:
    """Return a list of third-party packages required for the dashboard."""

    required = ("prompt_toolkit", "rich")
    return [name for name in required if importlib.util.find_spec(name) is None]


def _print_dependency_error(missing: list[str]) -> None:
    """Emit guidance for installing runtime dependencies."""

    message = dedent(
        f"""
        GNOMAN could not start because the following Python packages are missing:
            {', '.join(sorted(missing))}

        Install the project dependencies before launching the console, e.g.:
            python -m pip install -e .
        or install the published package:
            python -m pip install gnoman-cli
        """
    ).strip()
    print(message, file=sys.stderr)


def _render_splash() -> None:
    """Display the GNOMAN startup banner using Rich for colour output."""

    console = Console(highlight=False)
    console.print(f"[#00B7FF]{_BANNER}[/]", justify="center")
    console.print(
        f"[#00B7FF bold]GNOMAN Mission Control v{__version__}[/]",
        justify="center",
    )
    console.print(
        "[#7DF9FF]© 2025 Christopher Hirschauer — All Rights Reserved[/]",
        justify="center",
    )
    console.print(
        "[#39FF14]Licensed under GNOMAN License (see LICENSE.md)[/]",
        justify="center",
    )


def _launch_terminal() -> None:
    """Start the Prompt Toolkit dashboard once dependencies are confirmed."""

    missing = _missing_ui_dependencies()
    if missing:
        _print_dependency_error(missing)
        raise SystemExit(1)

    _render_splash()

    from .ui import TerminalUI

    try:
        append_record("ui.start", {"version": __version__}, True, {"mode": "terminal"})
    except (NotImplementedError, ValueError):
        # Audit signing is optional but encouraged.
        pass

    try:
        TerminalUI().run()
    finally:
        logging.shutdown()


def _launch_gui() -> None:
    """Start the lightweight Tkinter based GUI."""

    from .ui.simple_gui import SimpleGUI

    try:
        append_record("ui.start", {"version": __version__}, True, {"mode": "gui"})
    except (NotImplementedError, ValueError):
        pass

    SimpleGUI().run()


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Start GNOMAN Mission Control."""

    parser = argparse.ArgumentParser(description="GNOMAN mission control launcher")
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the experimental Tkinter GUI instead of the terminal dashboard.",
    )
    options = parser.parse_args(list(argv) if argv is not None else None)

    if options.gui:
        _launch_gui()
    else:
        _launch_terminal()


__all__ = ["main"]
