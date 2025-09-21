"""Curses TUI scaffolding for GNOMAN mission control."""

from __future__ import annotations

import curses

MENU_LINE = (
    "[S] Safe  [T] Tx  [C] Secrets  [Y] Sync  [A] Audit  "
    "[G] Graph  [U] Autopilot  [R] Rescue  [P] Plugins  [D] Guard"
)


def launch_tui() -> None:
    """Launch the minimal curses mission control interface."""

    def main(stdscr) -> None:
        curses.curs_set(0)
        stdscr.addstr(0, 0, "GNOMAN v0.3.0 Mission Control")
        stdscr.addstr(2, 0, MENU_LINE)
        stdscr.refresh()
        stdscr.getch()

    curses.wrapper(main)
