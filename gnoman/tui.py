"""Curses TUI scaffolding for GNOMAN mission control."""

from __future__ import annotations

import curses
from textwrap import wrap
from typing import Dict, List

MIN_HEIGHT = 18
MIN_WIDTH = 70

MenuItem = Dict[str, object]

MENU_ITEMS: List[MenuItem] = [
    {
        "key": "S",
        "title": "Safe",
        "tagline": "Coordinate Safe proposals and signature flow.",
        "description": (
            "Draft, sign, and execute Safe transactions while keeping quorum "
            "thresholds and owner health front of mind."
        ),
        "commands": [
            "gnoman safe propose --to <addr> --value <eth> --data <calldata>",
            "gnoman safe sign <proposal-id>",
            "gnoman safe exec <proposal-id>",
        ],
    },
    {
        "key": "T",
        "title": "Tx",
        "tagline": "Simulate execution and broadcast confidently.",
        "description": (
            "Build Safe payloads, simulate strategies against an Anvil fork, "
            "and execute pre-cleared proposals with traceability."
        ),
        "commands": [
            "gnoman tx simulate [<proposal-id>] [--plan plan.json]",
            "gnoman tx exec <proposal-id>",
            "gnoman tx simulate --trace",
        ],
    },
    {
        "key": "C",
        "title": "Secrets",
        "tagline": "Manage encrypted keyrings and vault entries.",
        "description": (
            "Rotate operator secrets, inspect stored credentials, and keep "
            "sensitive material in sync across environments."
        ),
        "commands": [
            "gnoman secrets list",
            "gnoman secrets add <KEY> <VALUE>",
            "gnoman secrets rotate <KEY>",
        ],
    },
    {
        "key": "Y",
        "title": "Sync",
        "tagline": "Reconcile .env, vault, and local state.",
        "description": (
            "Detect drift between secure storage, local secrets, and runtime "
            "configuration then reconcile it interactively or forcefully."
        ),
        "commands": [
            "gnoman sync",
            "gnoman sync --reconcile",
            "gnoman sync --force",
        ],
    },
    {
        "key": "A",
        "title": "Audit",
        "tagline": "Snapshot state for forensic record keeping.",
        "description": (
            "Generate signed JSON and PDF audit bundles detailing current "
            "balances, signers, and operational posture."
        ),
        "commands": [
            "gnoman audit",
        ],
    },
    {
        "key": "G",
        "title": "Graph",
        "tagline": "Visualise routing and liquidity insights.",
        "description": (
            "Render AES route graphs to SVG, PNG, or HTML to investigate "
            "liquidity flows and profitable pathways."
        ),
        "commands": [
            "gnoman graph view --format svg",
            "gnoman graph view --output custom/path",
        ],
    },
    {
        "key": "U",
        "title": "Autopilot",
        "tagline": "Assemble and validate the AES trading pipeline.",
        "description": (
            "Fetch loans, build trades, run ML validation, and queue or "
            "broadcast Safe payloads directly from mission control."
        ),
        "commands": [
            "gnoman autopilot --plan plan.json",
            "gnoman autopilot --dry-run",
            "gnoman autopilot --execute",
        ],
    },
    {
        "key": "R",
        "title": "Rescue",
        "tagline": "Guide incident response and safe recovery.",
        "description": (
            "Launch Safe recovery workflows, rotate signers, and freeze "
            "compromised wallets until a coordinated unfreeze."
        ),
        "commands": [
            "gnoman rescue safe <SAFE_ADDR>",
            "gnoman rotate all",
            "gnoman freeze <wallet|safe> <id>",
        ],
    },
    {
        "key": "P",
        "title": "Plugins",
        "tagline": "Curate optional integrations and tooling.",
        "description": (
            "List, install, remove, and hot-swap plugin packages while "
            "maintaining a forensic history of version changes."
        ),
        "commands": [
            "gnoman plugin list",
            "gnoman plugin add <name>",
            "gnoman plugin swap <name> <version>",
        ],
    },
    {
        "key": "D",
        "title": "Guard",
        "tagline": "Keep an eye on balances, quorum, and alerts.",
        "description": (
            "Run the System Guardian daemon to monitor gas, balances, "
            "thresholds, and arbitrage alerts on a cadence."
        ),
        "commands": [
            "gnoman guard",
            "gnoman guard --cycles 5",
        ],
    },
]

KEY_TO_INDEX = {
    ord(item["key"].lower()): idx for idx, item in enumerate(MENU_ITEMS)
}
KEY_TO_INDEX.update({ord(item["key"]): idx for idx, item in enumerate(MENU_ITEMS)})

QUIT_KEYS = {ord("q"), ord("Q"), 27}


def _wrap_text(text: str, width: int) -> List[str]:
    """Wrap ``text`` for the available ``width`` guarding against small panes."""

    if width <= 0:
        return []
    return wrap(text, width)


def _safe_addstr(win: "curses._CursesWindow", y: int, x: int, text: str, attr: int = 0) -> None:
    """Safely add ``text`` at ``(y, x)`` without raising ``curses.error``."""

    max_y, max_x = win.getmaxyx()
    if y < 0 or x < 0 or y >= max_y or x >= max_x:
        return
    available = max_x - x
    if available <= 0:
        return
    snippet = text[:available]
    try:
        win.addstr(y, x, snippet, attr)
    except curses.error:
        # Some terminals are strict about drawing on the bottom-right cell.
        pass


def _render_resize_hint(stdscr: "curses._CursesWindow", palette: Dict[str, int]) -> None:
    """Render a hint asking the operator to enlarge their terminal."""

    height, width = stdscr.getmaxyx()
    stdscr.erase()
    message = "GNOMAN needs at least 70x18 to render the dashboard."
    hint = "Resize your terminal or press Q to exit."
    row = max(0, height // 2 - 1)
    msg_col = max(0, (width - len(message)) // 2)
    hint_col = max(0, (width - len(hint)) // 2)
    _safe_addstr(stdscr, row, msg_col, message, palette["title"])
    _safe_addstr(stdscr, row + 2, hint_col, hint, palette["footer"])
    stdscr.refresh()


def _render_dashboard(
    stdscr: "curses._CursesWindow", selected: int, palette: Dict[str, int]
) -> bool:
    """Render the mission control dashboard."""

    stdscr.erase()
    height, width = stdscr.getmaxyx()

    if height < MIN_HEIGHT or width < MIN_WIDTH:
        _render_resize_hint(stdscr, palette)
        return False

    active = MENU_ITEMS[selected]
    menu_x = 2
    menu_width = max(24, min(32, width // 3 + 2))
    detail_x = menu_x + menu_width + 2
    detail_width = width - detail_x - 2
    separator_y = height - 4
    detail_limit = separator_y

    # Header
    _safe_addstr(stdscr, 0, 2, "GNOMAN Mission Control", palette["title"])
    version = "v0.3.0"
    _safe_addstr(stdscr, 0, max(2, width - len(version) - 2), version, palette["subtitle"])
    _safe_addstr(stdscr, 1, 2, "Guardian of Safes, Master of Keys", palette["subtitle"])
    if width > 2:
        _safe_addstr(stdscr, 2, 1, "-" * (width - 2), palette["subtitle"])

    # Menu column
    _safe_addstr(stdscr, 3, menu_x, "Modules", palette["detail_heading"])
    for idx, item in enumerate(MENU_ITEMS):
        y = 4 + idx
        if y >= detail_limit:
            break
        label = f"[{item['key']}] {item['title']}"
        padded = label[:menu_width].ljust(menu_width)
        _safe_addstr(stdscr, y, menu_x, " " * menu_width)
        if idx == selected:
            _safe_addstr(stdscr, y, menu_x, padded, palette["menu_active"])
        else:
            _safe_addstr(stdscr, y, menu_x, padded, palette["menu_inactive"])
            _safe_addstr(stdscr, y, menu_x + 1, item["key"], palette["menu_key"])

    # Divider between menu and detail panes
    divider_x = detail_x - 1
    for y in range(3, separator_y):
        _safe_addstr(stdscr, y, divider_x, "|", palette["subtitle"])

    # Detail pane
    detail_y = 3
    _safe_addstr(
        stdscr,
        detail_y,
        detail_x,
        f"{active['title']} module",
        palette["detail_heading"],
    )
    detail_y += 1
    for line in _wrap_text(str(active["description"]), detail_width):
        if detail_y >= detail_limit:
            break
        _safe_addstr(stdscr, detail_y, detail_x, line, palette["detail_text"])
        detail_y += 1

    commands = [str(cmd) for cmd in active.get("commands", [])]
    if commands and detail_y < detail_limit - 1:
        _safe_addstr(stdscr, detail_y, detail_x, "Key commands:", palette["detail_heading"])
        detail_y += 1
        for cmd in commands:
            if detail_y >= detail_limit:
                break
            wrapped = _wrap_text(cmd, detail_width - 4)
            if not wrapped:
                continue
            _safe_addstr(
                stdscr,
                detail_y,
                detail_x,
                f"- {wrapped[0]}",
                palette["detail_text"],
            )
            detail_y += 1
            for continuation in wrapped[1:]:
                if detail_y >= detail_limit:
                    break
                _safe_addstr(
                    stdscr,
                    detail_y,
                    detail_x + 2,
                    continuation,
                    palette["detail_text"],
                )
                detail_y += 1

    if separator_y < height and width > 2:
        _safe_addstr(stdscr, separator_y, 1, "-" * (width - 2), palette["subtitle"])

    # Status and footer
    status_width = max(0, width - 4)
    status_y = max(0, height - 3)
    if status_width > 0 and 0 <= status_y < height:
        _safe_addstr(stdscr, status_y, 2, " " * status_width)
        status_text = f"Active module: {active['title']} — {active['tagline']}"
        _safe_addstr(stdscr, status_y, 2, status_text[:status_width], palette["status"])

    footer_y = max(0, height - 2)
    if status_width > 0 and 0 <= footer_y < height and footer_y > status_y:
        footer_text = "Use arrow keys or hotkeys to explore • Press Q to exit"
        _safe_addstr(stdscr, footer_y, 2, " " * status_width)
        _safe_addstr(stdscr, footer_y, 2, footer_text[:status_width], palette["footer"])

    stdscr.refresh()
    return True


def launch_tui() -> None:
    """Launch the GNOMAN mission control curses interface."""

    def main(stdscr: "curses._CursesWindow") -> None:
        try:
            curses.curs_set(0)
        except curses.error:
            pass

        stdscr.nodelay(False)
        stdscr.keypad(True)

        palette: Dict[str, int] = {
            "title": curses.A_BOLD,
            "subtitle": curses.A_DIM,
            "menu_active": curses.A_REVERSE | curses.A_BOLD,
            "menu_inactive": curses.A_NORMAL,
            "menu_key": curses.A_BOLD,
            "detail_heading": curses.A_BOLD,
            "detail_text": curses.A_NORMAL,
            "status": curses.A_BOLD,
            "footer": curses.A_DIM,
        }

        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_CYAN, -1)
            curses.init_pair(2, curses.COLOR_MAGENTA, -1)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            curses.init_pair(4, curses.COLOR_GREEN, -1)
            palette["title"] = curses.color_pair(1) | curses.A_BOLD
            palette["menu_active"] = curses.color_pair(1) | curses.A_REVERSE | curses.A_BOLD
            palette["menu_key"] = curses.color_pair(2) | curses.A_BOLD
            palette["detail_heading"] = curses.color_pair(3) | curses.A_BOLD
            palette["status"] = curses.color_pair(4) | curses.A_BOLD
            palette["footer"] = curses.color_pair(2) | curses.A_DIM

        selected = 0
        while True:
            rendered = _render_dashboard(stdscr, selected, palette)
            key = stdscr.getch()

            if key in QUIT_KEYS:
                break
            if key == curses.KEY_RESIZE:
                continue
            if not rendered:
                # Ignore navigation until the terminal is big enough again.
                continue

            if key in KEY_TO_INDEX:
                selected = KEY_TO_INDEX[key]
                continue

            if key in {curses.KEY_DOWN, curses.KEY_RIGHT, ord("\t")}:
                selected = (selected + 1) % len(MENU_ITEMS)
            elif key in {curses.KEY_UP, curses.KEY_LEFT, getattr(curses, "KEY_BTAB", 353)}:
                selected = (selected - 1) % len(MENU_ITEMS)

    curses.wrapper(main)
