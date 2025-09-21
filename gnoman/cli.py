"""Bridge the packaged CLI entrypoint to the original interactive core."""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from . import core


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Launch the menu-driven interface from :mod:`gnoman.core`."""

    args = list(argv) if argv is not None else []
    if args:
        raise SystemExit("GNOMAN interactive CLI does not accept command-line arguments.")

    try:
        core.splash()
        core.main_menu()
    finally:
        core.logger.info("🧹 gnoman exiting via CLI adapter.")
        logging.shutdown()
