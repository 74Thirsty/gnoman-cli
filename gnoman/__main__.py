"""Console entrypoint bridging to :mod:`gnoman.cli`."""

from __future__ import annotations

from typing import Any, Optional

from .cli import main as cli_main


def main(argv: Optional[list[str]] = None) -> Any:
    """Delegate execution to :func:`gnoman.cli.main`."""

    return cli_main(argv)


if __name__ == "__main__":
    main()
