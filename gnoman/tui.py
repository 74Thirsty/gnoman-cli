"""Minimal placeholder TUI for GNOMAN."""

from __future__ import annotations

from textwrap import dedent


def launch_tui() -> None:
    """Display a short message guiding the operator to the CLI."""

    message = dedent(
        """
        GNOMAN Mission Control
        -----------------------
        The curses dashboard has been replaced by the modular CLI.

        Available command groups:
          * gnoman safe ...   – Safe orchestration and execution
          * gnoman wallet ... – Wallet derivation and vanity tools
          * gnoman sync ...   – Secret synchronisation and rotation
          * gnoman audit ...  – Forensic snapshot generation
          * gnoman abi ...    – ABI inspection and calldata encoding

        Run `gnoman --help` for full details.
        """
    )
    print(message)
