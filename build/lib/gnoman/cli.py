from __future__ import annotations

import sys
from typing import Optional

from rich.console import Console
from rich.panel import Panel

console = Console()

def _die(msg: str, code: int = 1) -> "NoReturn":  # type: ignore[name-defined]
    console.print(Panel.fit(f"[bold red]Error[/]: {msg}", border_style="red"))
    raise SystemExit(code)

def main(argv: Optional[list[str]] = None) -> None:
    """
    Entry point for the GNOMAN CLI.
    Tries to hand off to your existing interactive/menu function in core.py.
    """
    if argv is None:
        argv = sys.argv[1:]

    try:
        # Expect your current app entry to live here:
        # def main_menu() -> None: ...
        from .core import main_menu  # adjust if your entry is named differently
    except Exception as e:
        _die(f"Could not import GNOMAN core entry point: {e!r}")

    # If you later add argparse subcommands, parse argv here and route.
    # For now, just launch the interactive TUI.
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/]")
    except SystemExit:
        raise
    except Exception as e:
        _die(f"Unhandled exception while running GNOMAN: {e!r}")

