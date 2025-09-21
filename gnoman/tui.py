"""Curses TUI scaffolding for GNOMAN mission control."""

from __future__ import annotations

import curses
import io
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime
from textwrap import wrap
from types import SimpleNamespace
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from unittest import mock

from . import core
from .commands import (
    audit as audit_cmd,
    autopilot as autopilot_cmd,
    graph as graph_cmd,
    guard as guard_cmd,
    plugin as plugin_cmd,
    rescue as rescue_cmd,
    safe as safe_cmd,
    secrets as secrets_cmd,
    sync as sync_cmd,
    tx as tx_cmd,
)
from .utils import aes, logbook

MIN_HEIGHT = 18
MIN_WIDTH = 70

MenuItem = Dict[str, object]

MenuCallback = Callable[["MenuContext"], Optional[Sequence[str]]]
MenuEntry = Tuple[str, Optional[MenuCallback]]
MenuBuilder = Callable[["MenuContext"], Sequence[MenuEntry]]

LEGACY_BANNER_LINES: Tuple[str, ...] = (
    " ██████╗ ███╗   ██╗ ██████╗ ███╗   ███╗ █████╗ ███╗   ██╗",
    "██╔════╝ ████╗  ██║██╔═══██╗████╗ ████║██╔══██╗████╗  █║",
    "██║  ███╗██╔██╗ ██║██║   ██║██╔████╔██║███████║██╔██╗ ██║",
    "██║   ██║██║╚██╗██║██║   ██║██║╚██╔╝██║██╔══██║██║╚██╗██║",
    "╚██████╔╝██║ ╚████║╚██████╔╝██║ ╚═╝ ██║██║  ██║██║ ╚████║",
    " ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝",
    "",
    "        GNOMAN — Safe • Wallet • Keys • Hold24h",
    "        © 2025 Christopher Hirschauer — All Rights Reserved",
    "        Licensed under GNOMAN License (see LICENSE.md)",
    "───────────────────────────────────────────────────────────",
)

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
        "key": "W",
        "title": "Wallet",
        "tagline": "Operate HD wallets and hidden derivation trees.",
        "description": (
            "Generate or import mnemonic seeds, explore default and hidden "
            "account paths, and export discovered addresses with labels."
        ),
        "commands": [
            "Mission Control › Wallet",
            "Generate / import mnemonic",
            "Scan HD trees • Export wallet_export.json",
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
        "key": "K",
        "title": "Key Manager",
        "tagline": "Work directly with keyring-backed secrets.",
        "description": (
            "Add, retrieve, delete, or enumerate keyring entries just like the "
            "original GNOMAN console workflow."
        ),
        "commands": [
            "Mission Control › Key Manager",
            "Add / retrieve / delete secrets",
            "List keyring entries",
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
    {
        "key": "I",
        "title": "About",
        "tagline": "Review the GNOMAN license and provenance.",
        "description": (
            "Read the proprietary usage terms, authorship, and licensing "
            "details preserved from the original console splash screen."
        ),
        "commands": [
            "Mission Control › About & License",
        ],
    },
]

KEY_TO_INDEX = {
    ord(item["key"].lower()): idx for idx, item in enumerate(MENU_ITEMS)
}
KEY_TO_INDEX.update({ord(item["key"]): idx for idx, item in enumerate(MENU_ITEMS)})

QUIT_KEYS = {ord("q"), ord("Q"), 27}
ENTER_KEYS = {curses.KEY_ENTER, ord("\n"), ord("\r")}

DEFAULT_SAFE = "0xSAFECORE"


@dataclass
class MenuContext:
    """Runtime context shared between nested menus."""

    stdscr: "curses._CursesWindow"
    palette: Dict[str, int]
    stack: List[str] = field(default_factory=list)
    current_menu: str = ""


def _serialize(value: object) -> object:
    """Make ``value`` JSON-serialisable for forensic logging."""

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    return str(value)


def _menu_log(action: str, **fields: object) -> None:
    """Emit a forensic menu log entry with ``action`` and ``fields``."""

    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    payload = {key: _serialize(value) for key, value in fields.items()}
    details = " ".join(f"{key}={payload[key]}" for key in sorted(payload))
    message = f"[GNOMAN.Menu] {action}"
    if details:
        message = f"{message} {details}"
    record = {
        "timestamp": timestamp,
        "channel": "GNOMAN.Menu",
        "action": action,
        **payload,
        "message": message,
    }
    logbook.info(record)


def _key_repr(key: int) -> str:
    """Return a printable representation for ``key``."""

    if 0 <= key < 256:
        char = chr(key)
        if char.isprintable():
            return char
    return str(key)


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


def _clear_region(
    win: "curses._CursesWindow", top: int, left: int, height: int, width: int
) -> None:
    """Blank a rectangular region to avoid artefacts from previous frames."""

    if height <= 0 or width <= 0:
        return
    max_y, max_x = win.getmaxyx()
    start_y = max(0, top)
    end_y = min(max_y, top + height)
    start_x = max(0, left)
    if start_x >= max_x:
        return
    width = min(width, max_x - start_x)
    if width <= 0:
        return
    blank = " " * width
    for row in range(start_y, end_y):
        _safe_addstr(win, row, start_x, blank)


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


def _render_banner_screen(stdscr: "curses._CursesWindow", palette: Dict[str, int]) -> bool:
    """Display the legacy ASCII banner and wait for a key press."""

    while True:
        stdscr.erase()
        height, width = stdscr.getmaxyx()

        min_height = max(MIN_HEIGHT, len(LEGACY_BANNER_LINES) + 4)
        if height < min_height or width < MIN_WIDTH:
            _render_resize_hint(stdscr, palette)
            key = stdscr.getch()
            if key in QUIT_KEYS:
                return False
            if key == curses.KEY_RESIZE:
                continue
            continue

        for idx, line in enumerate(LEGACY_BANNER_LINES):
            attr = palette["title"] if idx < 6 else palette["subtitle"]
            col = max(0, (width - len(line)) // 2)
            _safe_addstr(stdscr, idx, col, line, attr)

        prompt = "Press any key to enter Mission Control"
        prompt_row = len(LEGACY_BANNER_LINES) + 1
        prompt_col = max(0, (width - len(prompt)) // 2)
        _safe_addstr(stdscr, prompt_row, prompt_col, prompt, palette["footer"])
        stdscr.refresh()

        key = stdscr.getch()
        if key == curses.KEY_RESIZE:
            continue
        if key in QUIT_KEYS:
            return False
        return True


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
    menu_start = 3
    items_start = menu_start + 1
    visible_rows = max(0, detail_limit - items_start)
    total_items = len(MENU_ITEMS)
    first_index = 0
    if visible_rows and visible_rows < total_items:
        first_index = min(max(0, selected - visible_rows + 1), total_items - visible_rows)
    last_index = total_items if not visible_rows else min(total_items, first_index + visible_rows)

    header_label = "Modules"
    if visible_rows and visible_rows < total_items:
        if first_index > 0:
            header_label = f"↑ {header_label}"
        if last_index < total_items:
            header_label = f"{header_label} ↓"
    _safe_addstr(stdscr, menu_start, menu_x, " " * menu_width)
    _safe_addstr(stdscr, menu_start, menu_x, header_label[:menu_width], palette["detail_heading"])

    for view_idx, item_idx in enumerate(range(first_index, last_index)):
        item = MENU_ITEMS[item_idx]
        y = items_start + view_idx
        label = f"[{item['key']}] {item['title']}"
        padded = label[:menu_width].ljust(menu_width)
        _safe_addstr(stdscr, y, menu_x, " " * menu_width)
        if item_idx == selected:
            _safe_addstr(stdscr, y, menu_x, padded, palette["menu_active"])
        else:
            _safe_addstr(stdscr, y, menu_x, padded, palette["menu_inactive"])
            _safe_addstr(stdscr, y, menu_x + 1, item["key"], palette["menu_key"])

    # Divider between menu and detail panes
    divider_x = detail_x - 1
    for y in range(3, separator_y):
        _safe_addstr(stdscr, y, divider_x, "|", palette["subtitle"])

    # Detail pane
    detail_top = 3
    if detail_width > 0:
        _clear_region(stdscr, detail_top, detail_x, max(0, separator_y - detail_top), detail_width)
    detail_y = detail_top
    _safe_addstr(
        stdscr,
        detail_y,
        detail_x,
        f"{active['title']} module",
        palette["detail_heading"],
    )
    detail_y += 1
    tagline = str(active.get("tagline") or "").strip()
    if tagline:
        for line in _wrap_text(tagline, detail_width):
            if detail_y >= detail_limit:
                break
            _safe_addstr(stdscr, detail_y, detail_x, line, palette["subtitle"])
            detail_y += 1
        if detail_y < detail_limit:
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


def _clear_input_line(ctx: MenuContext) -> None:
    """Blank the interactive input row for ``ctx``."""

    height, width = ctx.stdscr.getmaxyx()
    y = max(0, height - 4)
    _safe_addstr(ctx.stdscr, y, 0, " " * max(0, width))


def _render_submenu(
    ctx: MenuContext,
    title: str,
    items: Sequence[MenuEntry],
    selected: int,
    status_lines: Sequence[str],
) -> bool:
    """Render a submenu screen and return ``True`` when interactions allowed."""

    stdscr = ctx.stdscr
    palette = ctx.palette
    stdscr.erase()
    height, width = stdscr.getmaxyx()

    if height < MIN_HEIGHT or width < MIN_WIDTH:
        _render_resize_hint(stdscr, palette)
        return False

    header = ctx.current_menu or title
    _safe_addstr(stdscr, 0, 2, header[: max(0, width - 4)], palette["title"])
    hint = "Use arrows or numbers to move • Press Enter to select"
    _safe_addstr(stdscr, 1, 2, hint[: max(0, width - 4)], palette["subtitle"])

    menu_start = 3
    total = len(items)
    for idx, (label, _) in enumerate(items):
        prefix = "0" if idx == total - 1 and label.lower().startswith("back") else f"{idx + 1}"
        text = f"{prefix}. {label}"
        attr = palette["menu_active"] if idx == selected else palette["menu_inactive"]
        _safe_addstr(stdscr, menu_start + idx, 4, " " * max(0, width - 8))
        _safe_addstr(stdscr, menu_start + idx, 4, text[: max(0, width - 8)], attr)

    status_y = menu_start + total + 1
    bottom_limit = height - 5
    status_width = max(0, width - 8)
    if status_y <= bottom_limit and status_width > 0:
        _clear_region(stdscr, status_y, 4, max(0, bottom_limit - status_y + 1), status_width)
        if status_lines:
            _safe_addstr(stdscr, status_y, 4, "Last action:", palette["detail_heading"])
            status_y += 1
            for line in status_lines:
                for wrapped in _wrap_text(str(line), max(1, status_width - 2)):
                    if status_y > bottom_limit:
                        break
                    _safe_addstr(stdscr, status_y, 6, wrapped, palette["detail_text"])
                    status_y += 1

    footer_y = height - 2
    footer_text = "Press [q] to return"
    _safe_addstr(stdscr, footer_y, 2, " " * max(0, width - 4))
    _safe_addstr(stdscr, footer_y, 2, footer_text[: max(0, width - 4)], palette["footer"])

    _clear_input_line(ctx)
    stdscr.refresh()
    return True


def _prompt_input(
    ctx: MenuContext,
    prompt: str,
    *,
    default: Optional[str] = None,
    required: bool = False,
) -> Optional[str]:
    """Prompt for a string value and optionally enforce ``required`` input."""

    stdscr = ctx.stdscr
    height, width = stdscr.getmaxyx()
    label = prompt
    if default is not None and default != "":
        label = f"{prompt} [{default}]"
    max_label = max(10, width - 12)
    if len(label) > max_label:
        label = f"{label[: max_label - 3]}..."
    message = f"{label}: "
    input_y = max(0, height - 4)

    while True:
        _clear_input_line(ctx)
        _safe_addstr(stdscr, input_y, 2, message[: max(0, width - 4)], ctx.palette["detail_heading"])
        start_x = min(width - 3, 2 + len(message))
        max_chars = max(1, width - start_x - 2)
        curses.echo()
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        stdscr.move(input_y, start_x)
        stdscr.refresh()
        try:
            raw = stdscr.getstr(input_y, start_x, max_chars)
        except curses.error:
            raw = b""
        finally:
            curses.noecho()
            try:
                curses.curs_set(0)
            except curses.error:
                pass
        value = raw.decode("utf-8", errors="ignore").strip()
        _clear_input_line(ctx)

        if not value:
            if default is not None:
                return default
            if not required:
                return None
            curses.flash()
            _menu_log("prompt_missing", prompt=prompt, menu=ctx.current_menu)
            continue
        return value


def _prompt_secret(
    ctx: MenuContext,
    prompt: str,
    *,
    required: bool = False,
) -> Optional[str]:
    """Prompt for sensitive input without echoing characters."""

    stdscr = ctx.stdscr
    height, width = stdscr.getmaxyx()
    message = f"{prompt}: "
    input_y = max(0, height - 4)

    while True:
        _clear_input_line(ctx)
        _safe_addstr(stdscr, input_y, 2, message[: max(0, width - 4)], ctx.palette["detail_heading"])
        start_x = min(width - 3, 2 + len(message))
        max_chars = max(1, width - start_x - 2)
        curses.noecho()
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        stdscr.move(input_y, start_x)
        stdscr.refresh()
        try:
            raw = stdscr.getstr(input_y, start_x, max_chars)
        except curses.error:
            raw = b""
        finally:
            try:
                curses.curs_set(0)
            except curses.error:
                pass
        value = raw.decode("utf-8", errors="ignore").strip()
        _clear_input_line(ctx)

        if value:
            return value
        if not required:
            return None
        curses.flash()
        _menu_log("prompt_missing", prompt=prompt, menu=ctx.current_menu)


def _prompt_bool(ctx: MenuContext, prompt: str, *, default: bool = False) -> bool:
    """Prompt the operator for a boolean decision."""

    suffix = " [Y/n]" if default else " [y/N]"
    default_token = "y" if default else "n"
    while True:
        response = _prompt_input(
            ctx,
            f"{prompt}{suffix}",
            default=default_token,
            required=False,
        )
        if response is None:
            return default
        value = response.strip().lower()
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        curses.flash()
        _menu_log("invalid_input", prompt=prompt, value=value, menu=ctx.current_menu, kind="bool")


def _prompt_int(
    ctx: MenuContext,
    prompt: str,
    *,
    default: Optional[int] = None,
    minimum: Optional[int] = None,
) -> Optional[int]:
    """Prompt for an integer value respecting ``minimum`` when provided."""

    default_str = str(default) if default is not None else None
    while True:
        response = _prompt_input(
            ctx,
            prompt,
            default=default_str,
            required=default is None,
        )
        if response is None:
            return default
        try:
            value = int(response)
        except ValueError:
            curses.flash()
            _menu_log("invalid_input", prompt=prompt, value=response, menu=ctx.current_menu, kind="int")
            continue
        if minimum is not None and value < minimum:
            curses.flash()
            _menu_log(
                "invalid_input",
                prompt=prompt,
                value=value,
                menu=ctx.current_menu,
                kind="int",
                issue="lt_minimum",
                minimum=minimum,
            )
            continue
        return value


def _prompt_choice(
    ctx: MenuContext, prompt: str, choices: Sequence[str], *, default: Optional[str] = None
) -> Optional[str]:
    """Prompt for a value constrained to ``choices``."""

    display = "/".join(choices)
    base_prompt = f"{prompt} ({display})"
    while True:
        response = _prompt_input(
            ctx,
            base_prompt,
            default=default,
            required=default is None,
        )
        if response is None:
            return default
        value = response.strip().lower()
        for choice in choices:
            if value == choice.lower():
                return choice.lower()
        curses.flash()
        _menu_log("invalid_input", prompt=prompt, value=response, menu=ctx.current_menu, kind="choice")


@contextmanager
def _patched_prompts(
    *, inputs: Optional[Iterable[str]] = None, secrets: Optional[Iterable[str]] = None
) -> Iterable[str]:
    """Temporarily override ``input``/``getpass`` with canned values."""

    input_iter = iter(inputs or [])
    secret_iter = iter(secrets or [])

    def _next_input(_prompt: str = "") -> str:
        return next(input_iter, "")

    def _next_secret(_prompt: str = "") -> str:
        return next(secret_iter, "")

    with mock.patch("builtins.input", _next_input), mock.patch("getpass.getpass", _next_secret):
        yield


def _run_legacy_callable(
    func: Callable[..., object],
    *,
    inputs: Optional[Iterable[str]] = None,
    secrets: Optional[Iterable[str]] = None,
    args: Sequence[object] = (),
    kwargs: Optional[Dict[str, object]] = None,
) -> List[str]:
    """Execute ``func`` capturing stdout and optionally providing prompt input."""

    buffer = io.StringIO()
    call_kwargs = dict(kwargs or {})
    with _patched_prompts(inputs=inputs, secrets=secrets), redirect_stdout(buffer):
        func(*args, **call_kwargs)
    lines = [line.rstrip() for line in buffer.getvalue().splitlines() if line.strip()]
    if not lines:
        lines.append("Operation complete.")
    return lines


def _ensure_safe_initialised(ctx: MenuContext) -> None:
    """Ensure the legacy Safe context has been bootstrapped."""

    safe_ctx = getattr(core, "SAFE", None)
    if safe_ctx and getattr(safe_ctx, "contract", None) and getattr(safe_ctx, "addr", None):
        return
    try:
        core.safe_init()
    except RuntimeError:
        safe_address = _prompt_input(ctx, "Safe address", required=True)
        assert safe_address is not None
        with _patched_prompts(inputs=[safe_address]):
            core.safe_init()


def _invoke_command(
    callback: Callable[[SimpleNamespace], object], **kwargs: object
) -> Tuple[object, List[str]]:
    """Invoke ``callback`` with ``kwargs`` capturing its stdout output."""

    buffer = io.StringIO()
    args = SimpleNamespace(**kwargs)
    with redirect_stdout(buffer):
        result = callback(args)
    output = [line.rstrip() for line in buffer.getvalue().splitlines() if line.strip()]
    return result, output


def _open_submenu(ctx: MenuContext, title: str, builder: MenuBuilder) -> None:
    """Construct submenu entries via ``builder`` and run the menu loop."""

    items = list(builder(ctx))
    if not items or items[-1][1] is not None:
        items.append(("Back", None))
    _run_menu(ctx, title, items)


def _run_menu(ctx: MenuContext, title: str, items: Sequence[MenuEntry]) -> None:
    """Execute a submenu interaction loop for ``items``."""

    ctx.stack.append(title)
    ctx.current_menu = " › ".join(ctx.stack)
    _menu_log("enter", menu=ctx.current_menu)
    selected = 0
    status_lines: List[str] = []
    exit_reason = "return"

    try:
        while True:
            rendered = _render_submenu(ctx, title, items, selected, status_lines)
            key = ctx.stdscr.getch()

            if key in QUIT_KEYS:
                exit_reason = "quit"
                _menu_log("navigate", menu=ctx.current_menu, direction="quit")
                break
            if key == curses.KEY_RESIZE:
                continue
            if not rendered:
                continue

            if key in ENTER_KEYS:
                label, callback = items[selected]
                if callback is None:
                    exit_reason = "back"
                    _menu_log("navigate", menu=ctx.current_menu, selection=label, direction="back")
                    break
                _menu_log("select", menu=ctx.current_menu, selection=label)
                try:
                    result = callback(ctx)
                except Exception as exc:  # pragma: no cover - defensive guard
                    status_lines = [f"Error: {exc}"]
                    _menu_log("action_error", menu=ctx.current_menu, selection=label, error=str(exc))
                else:
                    if result is not None:
                        if isinstance(result, str):
                            status_lines = [result]
                        else:
                            status_lines = [str(line) for line in result if str(line).strip()]
                        if not status_lines:
                            status_lines = [f"{label} complete."]
                    _menu_log("action_complete", menu=ctx.current_menu, selection=label)
                continue

            if key in {curses.KEY_DOWN, curses.KEY_RIGHT, ord("\t")}:
                selected = (selected + 1) % len(items)
            elif key in {curses.KEY_UP, curses.KEY_LEFT, getattr(curses, "KEY_BTAB", 353)}:
                selected = (selected - 1) % len(items)
            elif ord("1") <= key <= ord("9"):
                index = key - ord("1")
                if index < len(items):
                    selected = index
                else:
                    curses.flash()
                    _menu_log("invalid_key", menu=ctx.current_menu, key=_key_repr(key))
            elif key == ord("0") and items:
                selected = len(items) - 1
            else:
                curses.flash()
                _menu_log("invalid_key", menu=ctx.current_menu, key=_key_repr(key))
    finally:
        path = ctx.current_menu
        _menu_log("exit", menu=path, reason=exit_reason)
        ctx.stack.pop()
        ctx.current_menu = " › ".join(ctx.stack)


def _action_safe_list(ctx: MenuContext) -> List[str]:
    """Display queued proposals for a Safe."""

    address = _prompt_input(ctx, "Safe address", default=DEFAULT_SAFE, required=False) or DEFAULT_SAFE
    record, output = _invoke_command(safe_cmd.status, safe_address=address)
    lines = list(output) if output else [f"Safe {address} status retrieved."]
    safe_info = record.get("safe", {}) if isinstance(record, dict) else {}
    proposals = safe_info.get("queued") or []
    if proposals:
        lines.append("Queued proposals:")
        for proposal in proposals:
            pid = proposal.get("id", "?")
            dest = proposal.get("to", "0x")
            value = proposal.get("value", "0")
            status = proposal.get("status", "pending")
            lines.append(f"  • #{pid} → {dest} {value} [{status}]")
    else:
        lines.append("No queued proposals.")
    return lines


def _action_safe_propose(ctx: MenuContext) -> List[str]:
    """Draft a new Safe proposal."""

    to_addr = _prompt_input(ctx, "Recipient address", required=True)
    value = _prompt_input(ctx, "ETH value", required=True)
    data = _prompt_input(ctx, "Calldata (optional)", default="0x", required=False) or "0x"
    record, output = _invoke_command(
        safe_cmd.propose,
        to=to_addr,
        value=value,
        data=data,
    )
    lines = output or [f"Drafted proposal to {to_addr} for {value}."]
    if isinstance(record, dict):
        proposal = record.get("proposal", {})
        if proposal:
            lines.append(
                "Proposal #{identifier} status={status}".format(
                    identifier=proposal.get("id", "?"),
                    status=proposal.get("status", "pending"),
                )
            )
    return lines


def _action_safe_sign(ctx: MenuContext) -> List[str]:
    """Sign a Safe proposal by identifier."""

    proposal_id = _prompt_input(ctx, "Proposal ID to sign", required=True)
    record, output = _invoke_command(safe_cmd.sign, proposal_id=proposal_id)
    lines = output or [f"Signed proposal {proposal_id}."]
    if isinstance(record, dict):
        proposal = record.get("proposal", {})
        if proposal:
            lines.append(f"Status → {proposal.get('status', 'unknown')}")
    return lines


def _action_safe_execute(ctx: MenuContext) -> List[str]:
    """Execute a Safe proposal by identifier."""

    proposal_id = _prompt_input(ctx, "Proposal ID to execute", required=True)
    record, output = _invoke_command(safe_cmd.exec, proposal_id=proposal_id)
    lines = output or [f"Executed proposal {proposal_id}."]
    if isinstance(record, dict):
        proposal = record.get("proposal", {})
        if proposal:
            lines.append(f"Status → {proposal.get('status', 'unknown')}")
    return lines


def _action_safe_status(ctx: MenuContext) -> List[str]:
    """Summarise Safe owners, threshold, and queue."""

    address = _prompt_input(ctx, "Safe address", default=DEFAULT_SAFE, required=False) or DEFAULT_SAFE
    record, output = _invoke_command(safe_cmd.status, safe_address=address)
    lines = output or [f"Status retrieved for {address}."]
    safe_info = record.get("safe", {}) if isinstance(record, dict) else {}
    owners = safe_info.get("owners") or []
    threshold = safe_info.get("threshold")
    queued = safe_info.get("queued") or []
    lines.append(f"Owners ({len(owners)}): {', '.join(owners) if owners else 'none'}")
    if threshold is not None:
        lines.append(f"Threshold: {threshold}")
    lines.append(f"Queued proposals: {len(queued)}")
    return lines


def _build_safe_proposals_menu(ctx: MenuContext) -> Sequence[MenuEntry]:
    return [
        ("List queued proposals", _action_safe_list),
        ("Draft new proposal", _action_safe_propose),
        ("Sign proposal", _action_safe_sign),
        ("Execute proposal", _action_safe_execute),
        ("Back", None),
    ]


def _enter_safe_proposals(ctx: MenuContext) -> Optional[Sequence[str]]:
    _open_submenu(ctx, "Safe › Proposals", _build_safe_proposals_menu)
    return None


def _build_safe_menu(ctx: MenuContext) -> Sequence[MenuEntry]:
    return [
        ("Proposal workflow", _enter_safe_proposals),
        ("Safe status overview", _action_safe_status),
        ("Legacy Safe operations", _show_safe_legacy_menu),
        ("Back", None),
    ]


def _build_safe_legacy_menu(ctx: MenuContext) -> Sequence[MenuEntry]:
    return [
        ("Show Safe info", _legacy_action_safe_info),
        ("Fund Safe with ETH", _legacy_action_safe_fund),
        ("Send ERC20 to Safe", _legacy_action_safe_send_erc20),
        ("Execute Safe transaction", _legacy_action_safe_exec),
        ("Add owner", _legacy_action_safe_add_owner),
        ("Remove owner", _legacy_action_safe_remove_owner),
        ("Change threshold", _legacy_action_safe_change_threshold),
        ("Add delegate", _legacy_action_safe_add_delegate),
        ("Remove delegate", _legacy_action_safe_remove_delegate),
        ("List delegates", _legacy_action_safe_list_delegates),
        ("Show guard", _legacy_action_safe_show_guard),
        ("Enable guard", _legacy_action_safe_enable_guard),
        ("Disable guard", _legacy_action_safe_disable_guard),
        ("Back", None),
    ]


def _show_safe_legacy_menu(ctx: MenuContext) -> None:
    _open_submenu(ctx, "Safe (Legacy)", _build_safe_legacy_menu)


def _legacy_action_safe_info(ctx: MenuContext) -> List[str]:
    _ensure_safe_initialised(ctx)
    return _run_legacy_callable(core.safe_show_info)


def _legacy_action_safe_fund(ctx: MenuContext) -> List[str]:
    _ensure_safe_initialised(ctx)
    amount = _prompt_input(ctx, "Amount ETH to send", required=True)
    assert amount is not None
    return _run_legacy_callable(core.safe_fund_eth, inputs=[amount])


def _legacy_action_safe_send_erc20(ctx: MenuContext) -> List[str]:
    _ensure_safe_initialised(ctx)
    token = _prompt_input(ctx, "ERC20 token address", required=True)
    amount = _prompt_input(ctx, "Amount of token", required=True)
    assert token is not None and amount is not None
    return _run_legacy_callable(core.safe_send_erc20, inputs=[token, amount])


def _legacy_action_safe_exec(ctx: MenuContext) -> List[str]:
    _ensure_safe_initialised(ctx)
    to_addr = _prompt_input(ctx, "Target address", required=True)
    assert to_addr is not None
    value_text = _prompt_input(ctx, "ETH value (default 0)", default="0", required=False) or "0"
    calldata = _prompt_input(ctx, "Calldata (0x…)", default="0x", required=False) or "0x"
    op_choice = _prompt_choice(ctx, "Operation type", ["0", "1"], default="0") or "0"

    try:
        checksum_to = core.Web3.to_checksum_address(to_addr)
    except ValueError as exc:  # pragma: no cover - validation guard
        raise ValueError("Invalid target address") from exc

    try:
        value_wei = int(core.Web3.to_wei(core.Decimal(value_text), "ether"))
    except Exception as exc:  # pragma: no cover - validation guard
        raise ValueError("Invalid ETH amount") from exc

    if calldata.lower() in {"", "0x"}:
        data_bytes = b""
    else:
        try:
            data_bytes = core.Web3.to_bytes(hexstr=calldata)
        except Exception as exc:  # pragma: no cover - validation guard
            raise ValueError("Invalid calldata hex") from exc

    safe_ctx = getattr(core, "SAFE", None)
    needed = getattr(safe_ctx, "threshold", 0) or 1
    signatures: List[str] = []
    for index in range(int(needed)):
        sig = _prompt_input(ctx, f"Signature {index + 1}/{needed}", required=True)
        assert sig is not None
        signatures.append(sig)

    return _run_legacy_callable(
        core.safe_exec_tx,
        args=[checksum_to, value_wei, data_bytes, int(op_choice)],
        inputs=signatures,
    )


def _legacy_action_safe_add_owner(ctx: MenuContext) -> List[str]:
    _ensure_safe_initialised(ctx)
    owner = _prompt_input(ctx, "New owner address", required=True)
    assert owner is not None
    return _run_legacy_callable(core.safe_add_owner, inputs=[owner])


def _legacy_action_safe_remove_owner(ctx: MenuContext) -> List[str]:
    _ensure_safe_initialised(ctx)
    target = _prompt_input(ctx, "Owner to remove", required=True)
    previous = _prompt_input(ctx, "Previous owner (linked list)", required=True)
    assert target is not None and previous is not None
    return _run_legacy_callable(core.safe_remove_owner, inputs=[target, previous])


def _legacy_action_safe_change_threshold(ctx: MenuContext) -> List[str]:
    _ensure_safe_initialised(ctx)
    threshold = _prompt_input(ctx, "New threshold (>0)", required=True)
    assert threshold is not None
    return _run_legacy_callable(core.safe_change_threshold, inputs=[threshold])


def _legacy_action_safe_add_delegate(ctx: MenuContext) -> List[str]:
    _ensure_safe_initialised(ctx)
    owner = _prompt_input(ctx, "Owner address", required=True)
    delegate = _prompt_input(ctx, "Delegate address", required=True)
    assert owner is not None and delegate is not None
    return _run_legacy_callable(core.safe_add_delegate, inputs=[owner, delegate])


def _legacy_action_safe_remove_delegate(ctx: MenuContext) -> List[str]:
    _ensure_safe_initialised(ctx)
    owner = _prompt_input(ctx, "Owner address", required=True)
    delegate = _prompt_input(ctx, "Delegate to remove", required=True)
    assert owner is not None and delegate is not None
    return _run_legacy_callable(core.safe_remove_delegate, inputs=[owner, delegate])


def _legacy_action_safe_list_delegates(ctx: MenuContext) -> List[str]:
    _ensure_safe_initialised(ctx)
    return _run_legacy_callable(core.safe_list_delegates)


def _legacy_action_safe_show_guard(ctx: MenuContext) -> List[str]:
    _ensure_safe_initialised(ctx)
    return _run_legacy_callable(core.safe_show_guard)


def _legacy_action_safe_enable_guard(ctx: MenuContext) -> List[str]:
    _ensure_safe_initialised(ctx)
    guard_addr = _prompt_input(ctx, "DelayGuard address", required=True)
    assert guard_addr is not None
    return _run_legacy_callable(core.safe_toggle_guard, inputs=[guard_addr], args=[True])


def _legacy_action_safe_disable_guard(ctx: MenuContext) -> List[str]:
    _ensure_safe_initialised(ctx)
    return _run_legacy_callable(core.safe_toggle_guard, args=[False])


def _action_tx_simulate(ctx: MenuContext) -> List[str]:
    proposal_id = _prompt_input(ctx, "Proposal ID (optional)", required=False)
    plan_path = _prompt_input(ctx, "Plan JSON path (optional)", required=False)
    include_trace = _prompt_bool(ctx, "Include execution trace?", default=False)
    ml_enabled = _prompt_bool(ctx, "Enable ML scoring?", default=True)
    record, output = _invoke_command(
        tx_cmd.simulate,
        proposal_id=proposal_id,
        plan=plan_path,
        trace=include_trace,
        ml_off=not ml_enabled,
    )
    lines = output or ["Simulation executed."]
    if isinstance(record, dict):
        lines.append(f"Plan digest: {record.get('plan_digest')}")
        lines.append(f"Gas used: {record.get('gas_used')}")
        success = record.get("success")
        if success is not None:
            lines.append(f"Success: {success}")
        trace_steps = record.get("trace") or []
        if trace_steps:
            lines.append("Trace steps:")
            lines.extend(f"  • {step}" for step in trace_steps)
    return lines


def _action_tx_exec(ctx: MenuContext) -> List[str]:
    proposal_id = _prompt_input(ctx, "Proposal ID to queue", required=True)
    record, output = _invoke_command(tx_cmd.exec, proposal_id=proposal_id)
    lines = output or [f"Execution payload queued for {proposal_id}."]
    if isinstance(record, dict):
        path = record.get("payload_path")
        if path:
            lines.append(f"Payload written to {path}")
    return lines


def _build_tx_menu(ctx: MenuContext) -> Sequence[MenuEntry]:
    return [
        ("Simulate Safe/DeFi plan", _action_tx_simulate),
        ("Queue execution payload", _action_tx_exec),
        ("Back", None),
    ]


def _legacy_action_wallet_generate(ctx: MenuContext) -> List[str]:
    return _run_legacy_callable(core.wal_generate_mnemonic)


def _legacy_action_wallet_import(ctx: MenuContext) -> List[str]:
    mnemonic = _prompt_secret(ctx, "Enter mnemonic", required=True)
    assert mnemonic is not None
    return _run_legacy_callable(core.wal_import_mnemonic, secrets=[mnemonic])


def _legacy_action_wallet_passphrase(ctx: MenuContext) -> List[str]:
    passphrase = _prompt_secret(ctx, "Passphrase (blank clears)", required=False) or ""
    return _run_legacy_callable(core.wal_set_passphrase, secrets=[passphrase])


def _legacy_action_wallet_preview(ctx: MenuContext) -> List[str]:
    path = _prompt_input(ctx, "Derivation path", required=True)
    assert path is not None
    return _run_legacy_callable(core.wal_preview, inputs=[path])


def _legacy_action_wallet_scan_default(ctx: MenuContext) -> List[str]:
    count = _prompt_int(ctx, "How many accounts", default=5, minimum=1) or 5
    return _run_legacy_callable(core.wal_scan, args=[count, False])


def _legacy_action_wallet_scan_hidden(ctx: MenuContext) -> List[str]:
    count = _prompt_int(ctx, "How many hidden accounts", default=5, minimum=1) or 5
    return _run_legacy_callable(core.wal_scan, args=[count, True])


def _legacy_action_wallet_derive(ctx: MenuContext) -> List[str]:
    path = _prompt_input(ctx, "Path (e.g., m/44'/60'/0'/0/1)", required=True)
    assert path is not None
    address, _account = core.wal_derive(path)
    if address:
        return [f"{path} -> {address}"]
    return [f"Failed to derive address for {path}"]


def _legacy_action_wallet_export(ctx: MenuContext) -> List[str]:
    return _run_legacy_callable(core.wal_export_discovered)


def _legacy_action_wallet_label(ctx: MenuContext) -> List[str]:
    address = _prompt_input(ctx, "Address to label", required=True)
    label = _prompt_input(ctx, "Label", required=True)
    assert address is not None and label is not None
    return _run_legacy_callable(core.wal_label, inputs=[address, label])


def _build_wallet_menu(ctx: MenuContext) -> Sequence[MenuEntry]:
    return [
        ("Generate mnemonic", _legacy_action_wallet_generate),
        ("Import mnemonic", _legacy_action_wallet_import),
        ("Set or clear passphrase", _legacy_action_wallet_passphrase),
        ("Preview address (any path)", _legacy_action_wallet_preview),
        ("Scan default accounts", _legacy_action_wallet_scan_default),
        ("Scan hidden HD tree", _legacy_action_wallet_scan_hidden),
        ("Derive specific path", _legacy_action_wallet_derive),
        ("Export discovered addresses", _legacy_action_wallet_export),
        ("Label address", _legacy_action_wallet_label),
        ("Back", None),
    ]


def _action_secrets_list(ctx: MenuContext) -> List[str]:
    record, output = _invoke_command(secrets_cmd.list_secrets)
    lines = list(output) if output else ["Retrieved secrets snapshot."]
    if isinstance(record, dict):
        entries = record.get("entries") or []
        if entries:
            for entry in entries:
                sources = ", ".join(entry.get("sources", [])) or "no sources"
                lines.append(f"{entry.get('key')}: {entry.get('status', 'unknown')} ({sources})")
        else:
            lines.append("No secrets tracked yet.")
    return lines


def _action_secrets_add(ctx: MenuContext) -> List[str]:
    key = _prompt_input(ctx, "Secret key", required=True)
    value = _prompt_input(ctx, "Secret value", required=True)
    record, output = _invoke_command(secrets_cmd.add_secret, key=key, value=value)
    lines = output or [f"Stored secret {key}."]
    if isinstance(record, dict):
        lines.append(f"Status: {record.get('status', 'stored')}")
    return lines


def _action_secrets_rotate(ctx: MenuContext) -> List[str]:
    key = _prompt_input(ctx, "Secret key to rotate", required=True)
    record, output = _invoke_command(secrets_cmd.rotate_secret, key=key)
    lines = output or [f"Rotated secret {key}."]
    if isinstance(record, dict):
        preview = record.get("preview")
        if preview:
            lines.append(f"Preview: {preview}")
    return lines


def _action_secrets_remove(ctx: MenuContext) -> List[str]:
    key = _prompt_input(ctx, "Secret key to remove", required=True)
    record, output = _invoke_command(secrets_cmd.remove_secret, key=key)
    lines = output or [f"Removal attempted for {key}."]
    if isinstance(record, dict):
        lines.append(f"Status: {record.get('status', 'removed')}")
    return lines


def _build_secrets_menu(ctx: MenuContext) -> Sequence[MenuEntry]:
    return [
        ("List tracked secrets", _action_secrets_list),
        ("Add secret", _action_secrets_add),
        ("Rotate secret", _action_secrets_rotate),
        ("Remove secret", _action_secrets_remove),
        ("Back", None),
    ]


def _legacy_action_key_add(ctx: MenuContext) -> List[str]:
    key = _prompt_input(ctx, "Secret key (e.g., RPC_URL)", required=True)
    value = _prompt_secret(ctx, "Secret value", required=True)
    assert key is not None and value is not None
    return _run_legacy_callable(core.km_add, inputs=[key], secrets=[value])


def _legacy_action_key_get(ctx: MenuContext) -> List[str]:
    key = _prompt_input(ctx, "Secret key", required=True)
    assert key is not None
    return _run_legacy_callable(core.km_get, inputs=[key])


def _legacy_action_key_delete(ctx: MenuContext) -> List[str]:
    key = _prompt_input(ctx, "Secret key to delete", required=True)
    assert key is not None
    return _run_legacy_callable(core.km_del, inputs=[key])


def _legacy_action_key_list(ctx: MenuContext) -> List[str]:
    return _run_legacy_callable(core.km_list_keyring)


def _build_key_manager_menu(ctx: MenuContext) -> Sequence[MenuEntry]:
    return [
        ("Add or update secret", _legacy_action_key_add),
        ("Retrieve secret", _legacy_action_key_get),
        ("Delete secret", _legacy_action_key_delete),
        ("List keyring entries", _legacy_action_key_list),
        ("Back", None),
    ]


def _action_sync_inspect(ctx: MenuContext) -> List[str]:
    coordinator = aes.get_secrets_coordinator()
    snapshot = coordinator.snapshot()
    drift = coordinator.detect_drift(snapshot)
    status = "in-sync" if not drift else "drift"
    logbook.info({"action": "sync_inspect", "status": status, "drift": drift})
    if not drift:
        return ["All secret stores aligned across environments."]
    lines = ["Drift detected across stores:"]
    for key, stores in drift.items():
        store_values = ", ".join(f"{name}={value}" for name, value in stores.items())
        lines.append(f"  • {key}: {store_values}")
    return lines


def _action_sync_reconcile(ctx: MenuContext) -> List[str]:
    record, output = _invoke_command(sync_cmd.run, force=False, reconcile=True)
    lines = output or ["Priority reconciliation complete."]
    if isinstance(record, dict):
        operations = record.get("operations") or []
        lines.append(f"Applied {len(operations)} updates across stores.")
    return lines


def _action_sync_force(ctx: MenuContext) -> List[str]:
    record, output = _invoke_command(sync_cmd.run, force=True, reconcile=False)
    lines = output or ["Force sync applied across all stores."]
    if isinstance(record, dict):
        result = record.get("result") or {}
        lines.append(f"Stores harmonised: {len(result)}")
    return lines


def _build_sync_menu(ctx: MenuContext) -> Sequence[MenuEntry]:
    return [
        ("Inspect drift", _action_sync_inspect),
        ("Reconcile using priority order", _action_sync_reconcile),
        ("Force sync now", _action_sync_force),
        ("Back", None),
    ]


def _action_audit_snapshot(ctx: MenuContext) -> List[str]:
    record, output = _invoke_command(audit_cmd.run)
    lines = output or ["Audit snapshot generated."]
    if isinstance(record, dict):
        json_path = record.get("json_path")
        pdf_path = record.get("pdf_path")
        if json_path:
            lines.append(f"JSON report: {json_path}")
        if pdf_path:
            lines.append(f"PDF report: {pdf_path}")
    return lines


def _build_audit_menu(ctx: MenuContext) -> Sequence[MenuEntry]:
    return [
        ("Generate forensic snapshot", _action_audit_snapshot),
        ("Back", None),
    ]


def _make_graph_action(fmt: str) -> MenuCallback:
    def _action(ctx: MenuContext) -> List[str]:
        output_path = _prompt_input(ctx, "Custom output path (optional)", required=False)
        record, output = _invoke_command(graph_cmd.view, format=fmt, output=output_path)
        lines = output or [f"Rendered {fmt} graph."]
        if isinstance(record, dict):
            path = record.get("path")
            if path:
                lines.append(f"Saved to {path}")
            highlighted = record.get("highlighted") or record.get("highlighted_routes") or []
            if highlighted:
                lines.append(f"Highlighted routes: {len(highlighted)}")
        return lines

    return _action


def _build_graph_menu(ctx: MenuContext) -> Sequence[MenuEntry]:
    return [
        ("Render SVG", _make_graph_action("svg")),
        ("Render HTML", _make_graph_action("html")),
        ("Render PNG", _make_graph_action("png")),
        ("Back", None),
    ]


def _make_autopilot_action(mode: str) -> MenuCallback:
    def _action(ctx: MenuContext) -> List[str]:
        plan_path = _prompt_input(ctx, "Plan JSON path (optional)", required=False)
        flags = {"dry_run": False, "execute": False, "alerts_only": False}
        if mode == "dry-run":
            flags["dry_run"] = True
        elif mode == "execute":
            flags["execute"] = True
        elif mode == "alerts":
            flags["alerts_only"] = True
        record, output = _invoke_command(
            autopilot_cmd.run,
            plan=plan_path,
            dry_run=flags["dry_run"],
            execute=flags["execute"],
            alerts_only=flags["alerts_only"],
        )
        lines = output or [f"Autopilot completed in {mode} mode."]
        if isinstance(record, dict):
            lines.append(f"Mode: {record.get('mode')}")
            steps = record.get("steps") or []
            if steps:
                lines.append(f"Steps executed: {len(steps)}")
        return lines

    return _action


def _build_autopilot_menu(ctx: MenuContext) -> Sequence[MenuEntry]:
    return [
        ("Queue autopilot workflow", _make_autopilot_action("queue")),
        ("Dry-run autopilot", _make_autopilot_action("dry-run")),
        ("Execute autopilot now", _make_autopilot_action("execute")),
        ("Alerts-only run", _make_autopilot_action("alerts")),
        ("Back", None),
    ]


def _action_rescue_safe(ctx: MenuContext) -> List[str]:
    safe_address = _prompt_input(ctx, "Safe address", default=DEFAULT_SAFE, required=False) or DEFAULT_SAFE
    record, output = _invoke_command(rescue_cmd.rescue_safe, safe_address=safe_address)
    lines = output or [f"Recovery wizard started for {safe_address}."]
    if isinstance(record, dict):
        steps = record.get("steps") or []
        if steps:
            lines.append("Recovery steps:")
            lines.extend(f"  • {step}" for step in steps)
    return lines


def _action_rescue_rotate(ctx: MenuContext) -> List[str]:
    record, output = _invoke_command(rescue_cmd.rotate_all)
    lines = output or ["Rotation complete."]
    if isinstance(record, dict):
        owners = record.get("owners") or []
        if owners:
            lines.append(f"New owners: {', '.join(owners)}")
    return lines


def _action_rescue_freeze(ctx: MenuContext) -> List[str]:
    target_type = _prompt_choice(ctx, "Target type", ["wallet", "safe"], default="wallet")
    target_id = _prompt_input(ctx, "Target identifier", required=True)
    reason = _prompt_input(ctx, "Reason", default="incident response", required=False) or "incident response"
    record, output = _invoke_command(
        rescue_cmd.freeze,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
    )
    lines = output or [f"{target_type} {target_id} frozen."]
    if isinstance(record, dict):
        token = record.get("unfreeze_token")
        if token:
            lines.append(f"Unfreeze token: {token}")
    return lines


def _build_rescue_menu(ctx: MenuContext) -> Sequence[MenuEntry]:
    return [
        ("Start Safe recovery", _action_rescue_safe),
        ("Rotate all signers", _action_rescue_rotate),
        ("Freeze wallet or Safe", _action_rescue_freeze),
        ("Back", None),
    ]


def _action_plugin_list(ctx: MenuContext) -> List[str]:
    record, output = _invoke_command(plugin_cmd.list_plugins)
    lines = output or ["Plugin registry snapshot fetched."]
    if isinstance(record, dict):
        plugins = record.get("plugins") or []
        if plugins:
            for entry in plugins:
                lines.append(f"{entry.get('name')}@{entry.get('version')} ({entry.get('schema', 'n/a')})")
        else:
            lines.append("No plugins installed.")
    return lines


def _action_plugin_add(ctx: MenuContext) -> List[str]:
    name = _prompt_input(ctx, "Plugin name", required=True)
    record, output = _invoke_command(plugin_cmd.add_plugin, name=name)
    lines = output or [f"Registered plugin {name}."]
    if isinstance(record, dict):
        plugin = record.get("plugin") or {}
        if plugin:
            lines.append(f"Version: {plugin.get('version', 'v1.0')}")
    return lines


def _action_plugin_remove(ctx: MenuContext) -> List[str]:
    name = _prompt_input(ctx, "Plugin name to remove", required=True)
    record, output = _invoke_command(plugin_cmd.remove_plugin, name=name)
    lines = output or [f"Removal attempted for {name}."]
    if isinstance(record, dict):
        plugin = record.get("plugin") or {}
        removed = plugin.get("removed")
        lines.append("Removed." if removed else "Plugin missing.")
    return lines


def _action_plugin_swap(ctx: MenuContext) -> List[str]:
    name = _prompt_input(ctx, "Plugin name", required=True)
    version = _prompt_input(ctx, "Target version", required=True)
    record, output = _invoke_command(plugin_cmd.swap, name=name, version=version)
    lines = output or [f"Swap attempted for {name}."]
    if isinstance(record, dict):
        status = record.get("status")
        lines.append(f"Status: {status}")
        plugin = record.get("plugin") or {}
        previous = plugin.get("previous_version")
        if previous:
            lines.append(f"{name}: {previous} → {plugin.get('version')}")
    return lines


def _build_plugins_menu(ctx: MenuContext) -> Sequence[MenuEntry]:
    return [
        ("List plugins", _action_plugin_list),
        ("Add plugin", _action_plugin_add),
        ("Remove plugin", _action_plugin_remove),
        ("Swap plugin version", _action_plugin_swap),
        ("Back", None),
    ]


def _action_guard_run(ctx: MenuContext) -> List[str]:
    cycles = _prompt_int(ctx, "Number of guard cycles", default=3, minimum=1) or 3
    record, output = _invoke_command(guard_cmd.run, cycles=cycles)
    lines = output or [f"Guardian executed for {cycles} cycle(s)."]
    if isinstance(record, dict):
        alerts = record.get("alerts") or []
        if alerts:
            lines.append(f"Alerts: {', '.join(alerts)}")
        else:
            lines.append("No alerts raised.")
    return lines


def _build_guard_menu(ctx: MenuContext) -> Sequence[MenuEntry]:
    return [
        ("Run monitoring cycles", _action_guard_run),
        ("Back", None),
    ]


def _legacy_action_about(ctx: MenuContext) -> List[str]:
    return _run_legacy_callable(core.about_menu)


def _show_safe_menu(ctx: MenuContext) -> None:
    _open_submenu(ctx, "Safe", _build_safe_menu)


def _show_tx_menu(ctx: MenuContext) -> None:
    _open_submenu(ctx, "Tx", _build_tx_menu)


def _show_wallet_menu(ctx: MenuContext) -> None:
    _open_submenu(ctx, "Wallet", _build_wallet_menu)


def _show_secrets_menu(ctx: MenuContext) -> None:
    _open_submenu(ctx, "Secrets", _build_secrets_menu)


def _show_key_manager_menu(ctx: MenuContext) -> None:
    _open_submenu(ctx, "Key Manager", _build_key_manager_menu)


def _show_sync_menu(ctx: MenuContext) -> None:
    _open_submenu(ctx, "Sync", _build_sync_menu)


def _show_audit_menu(ctx: MenuContext) -> None:
    _open_submenu(ctx, "Audit", _build_audit_menu)


def _show_graph_menu(ctx: MenuContext) -> None:
    _open_submenu(ctx, "Graph", _build_graph_menu)


def _show_autopilot_menu(ctx: MenuContext) -> None:
    _open_submenu(ctx, "Autopilot", _build_autopilot_menu)


def _show_rescue_menu(ctx: MenuContext) -> None:
    _open_submenu(ctx, "Rescue", _build_rescue_menu)


def _show_plugins_menu(ctx: MenuContext) -> None:
    _open_submenu(ctx, "Plugins", _build_plugins_menu)


def _show_guard_menu(ctx: MenuContext) -> None:
    _open_submenu(ctx, "Guard", _build_guard_menu)


def _show_about_menu(ctx: MenuContext) -> None:
    ctx.stack.append("About")
    ctx.current_menu = " › ".join(ctx.stack)
    _menu_log("enter", menu=ctx.current_menu)

    stdscr = ctx.stdscr
    palette = ctx.palette
    about_lines = _legacy_action_about(ctx)
    exit_reason = "return"

    try:
        while True:
            stdscr.erase()
            height, width = stdscr.getmaxyx()

            if height < MIN_HEIGHT or width < MIN_WIDTH:
                _render_resize_hint(stdscr, palette)
                key = stdscr.getch()
                if key in QUIT_KEYS:
                    exit_reason = "quit"
                    break
                if key == curses.KEY_RESIZE:
                    continue
                continue

            row = 0
            for idx, line in enumerate(LEGACY_BANNER_LINES):
                attr = palette["title"] if idx < 6 else palette["subtitle"]
                col = max(0, (width - len(line)) // 2)
                _safe_addstr(stdscr, row, col, line, attr)
                row += 1

            row += 1
            text_width = max(0, width - 4)
            for line in about_lines:
                for wrapped in _wrap_text(line, text_width):
                    if row >= height - 3:
                        break
                    _safe_addstr(stdscr, row, 2, wrapped, palette["detail_text"])
                    row += 1
                if row >= height - 3:
                    break

            footer = "Press Enter or Q to return"
            footer_col = max(0, (width - len(footer)) // 2)
            _safe_addstr(stdscr, height - 2, footer_col, footer, palette["footer"])

            stdscr.refresh()
            key = stdscr.getch()
            if key in QUIT_KEYS:
                exit_reason = "quit"
                break
            if key in ENTER_KEYS:
                break
            if key == curses.KEY_RESIZE:
                continue
    finally:
        _menu_log("exit", menu=ctx.current_menu, reason=exit_reason)
        ctx.stack.pop()
        ctx.current_menu = " › ".join(ctx.stack)


SUBMENU_DISPATCH: Dict[str, Callable[[MenuContext], None]] = {
    "Safe": _show_safe_menu,
    "Tx": _show_tx_menu,
    "Wallet": _show_wallet_menu,
    "Secrets": _show_secrets_menu,
    "Key Manager": _show_key_manager_menu,
    "Sync": _show_sync_menu,
    "Audit": _show_audit_menu,
    "Graph": _show_graph_menu,
    "Autopilot": _show_autopilot_menu,
    "Rescue": _show_rescue_menu,
    "Plugins": _show_plugins_menu,
    "Guard": _show_guard_menu,
    "About": _show_about_menu,
}


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

        context = MenuContext(stdscr=stdscr, palette=palette)

        if not _render_banner_screen(stdscr, palette):
            return

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

            if key in ENTER_KEYS:
                item = MENU_ITEMS[selected]
                handler = SUBMENU_DISPATCH.get(str(item.get("title")))
                if handler is not None:
                    context.stdscr = stdscr
                    context.palette = palette
                    context.stack.clear()
                    context.current_menu = ""
                    handler(context)
                else:
                    _menu_log("missing_submenu", menu=item.get("title"))
                continue

            if key in {curses.KEY_DOWN, curses.KEY_RIGHT, ord("\t")}:
                selected = (selected + 1) % len(MENU_ITEMS)
            elif key in {curses.KEY_UP, curses.KEY_LEFT, getattr(curses, "KEY_BTAB", 353)}:
                selected = (selected - 1) % len(MENU_ITEMS)

    curses.wrapper(main)
