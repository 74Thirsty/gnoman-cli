"""Curses TUI scaffolding for GNOMAN mission control."""

from __future__ import annotations

import curses
import io
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime
from textwrap import wrap
from types import SimpleNamespace
from typing import Callable, Dict, List, Optional, Sequence, Tuple

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
    if status_lines and status_y <= bottom_limit:
        _safe_addstr(stdscr, status_y, 4, "Last action:", palette["detail_heading"])
        status_y += 1
        for line in status_lines:
            for wrapped in _wrap_text(str(line), max(0, width - 10)):
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
        ("Back", None),
    ]


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


def _show_safe_menu(ctx: MenuContext) -> None:
    _open_submenu(ctx, "Safe", _build_safe_menu)


def _show_tx_menu(ctx: MenuContext) -> None:
    _open_submenu(ctx, "Tx", _build_tx_menu)


def _show_secrets_menu(ctx: MenuContext) -> None:
    _open_submenu(ctx, "Secrets", _build_secrets_menu)


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


SUBMENU_DISPATCH: Dict[str, Callable[[MenuContext], None]] = {
    "Safe": _show_safe_menu,
    "Tx": _show_tx_menu,
    "Secrets": _show_secrets_menu,
    "Sync": _show_sync_menu,
    "Audit": _show_audit_menu,
    "Graph": _show_graph_menu,
    "Autopilot": _show_autopilot_menu,
    "Rescue": _show_rescue_menu,
    "Plugins": _show_plugins_menu,
    "Guard": _show_guard_menu,
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
