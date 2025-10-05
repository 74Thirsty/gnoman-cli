"""Console entrypoint bridging to :mod:`gnoman.app`."""

from __future__ import annotations

from typing import Any, Optional

from .app import main as app_main


def main(argv: Optional[list[str]] = None) -> Any:
    """Delegate execution to :func:`gnoman.app.main`."""

    return app_main()


if __name__ == "__main__":
    main()
