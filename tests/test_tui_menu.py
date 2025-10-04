"""Tests for the curses menu scaffolding that avoid heavy core imports."""

from __future__ import annotations

import sys
import types
from typing import Iterable, List

import pytest


class FakeWindow:
    """Minimal curses window stub capturing drawn content for assertions."""

    def __init__(self, *, height: int = 24, width: int = 80, inputs: Iterable[int] | None = None) -> None:
        self.height = height
        self.width = width
        self._inputs: List[int] = list(inputs or [])
        self.buffer: List[List[str]] = [[" "] * width for _ in range(height)]
        self.cursor = (0, 0)

    # Curses window interface -------------------------------------------------
    def getmaxyx(self) -> tuple[int, int]:
        return self.height, self.width

    def erase(self) -> None:
        for row in range(self.height):
            self.buffer[row] = [" "] * self.width

    def addstr(self, y: int, x: int, text: str, _attr: int = 0) -> None:
        if y < 0 or y >= self.height:
            return
        if x < 0 or x >= self.width:
            return
        limit = min(self.width - x, len(text))
        for idx in range(limit):
            self.buffer[y][x + idx] = text[idx]

    def refresh(self) -> None:  # pragma: no cover - invoked but no behaviour
        return

    def getch(self) -> int:
        if self._inputs:
            return self._inputs.pop(0)
        return ord("q")

    def move(self, y: int, x: int) -> None:  # pragma: no cover - not used in assertions
        self.cursor = (y, x)

    def getstr(self, _y: int, _x: int, _n: int) -> bytes:  # pragma: no cover - not exercised
        return b""

    # Helpers ----------------------------------------------------------------
    def line(self, y: int) -> str:
        return "".join(self.buffer[y])


# Provide a very small stub for gnoman.core before importing the TUI module.
sys.modules["gnoman.core"] = types.SimpleNamespace()

from gnoman import tui  # noqa: E402  (import after core stub injection)


def _palette() -> dict[str, int]:
    return {
        "title": 0,
        "subtitle": 0,
        "menu_active": 0,
        "menu_inactive": 0,
        "menu_key": 0,
        "detail_heading": 0,
        "detail_text": 0,
        "status": 0,
        "footer": 0,
    }


def test_core_not_loaded_on_import() -> None:
    assert tui._CORE_MODULE is None


def test_root_menu_path_is_clean() -> None:
    window = FakeWindow(inputs=[ord("q")])
    ctx = tui.MenuContext(stdscr=window, palette=_palette())
    tui._run_menu(ctx, "Safe", [("Back", None)])

    header = window.line(0)
    assert "Safe" in header
    assert "Safe › Safe" not in header
    assert ctx.stack == []
    assert ctx.current_menu == ""


def test_nested_menu_deduplicates_parent_breadcrumbs() -> None:
    window = FakeWindow(inputs=[ord("q")])
    ctx = tui.MenuContext(stdscr=window, palette=_palette(), stack=["Safe"], current_menu="Safe")

    tui._run_menu(ctx, "Safe › Proposals", [("Back", None)])

    header = window.line(0)
    assert "Safe › Proposals" in header
    assert "Safe › Safe › Proposals" not in header
    assert ctx.stack == ["Safe"]
    assert ctx.current_menu == "Safe"


def test_menu_items_have_dispatch_handlers() -> None:
    top_level_titles = {item["title"] for item in tui.MENU_ITEMS}
    assert top_level_titles == set(tui.SUBMENU_DISPATCH)


def test_submenu_dispatch_registers_back_option(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, list[tuple[str, object | None]]] = {}

    def _fake_open_submenu(ctx: tui.MenuContext, title: str, builder):
        entries = list(builder(ctx))
        assert entries, f"{title} must define at least one entry"
        label, callback = entries[-1]
        assert callback is None
        assert label.lower().startswith("back"), "Last entry should be a Back option"
        captured[title] = entries

    monkeypatch.setattr(tui, "_open_submenu", _fake_open_submenu)

    ctx = tui.MenuContext(stdscr=FakeWindow(inputs=[ord("q")]), palette=_palette())
    for title, handler in tui.SUBMENU_DISPATCH.items():
        if title == "About":
            continue
        ctx.stack.clear()
        ctx.current_menu = ""
        handler(ctx)

    expected = {title for title in tui.SUBMENU_DISPATCH if title != "About"}
    assert set(captured) == expected


def test_about_menu_renders_and_restores_context(monkeypatch: pytest.MonkeyPatch) -> None:
    window = FakeWindow(inputs=[ord("\n")])
    ctx = tui.MenuContext(stdscr=window, palette=_palette())

    monkeypatch.setattr(tui, "_legacy_action_about", lambda _ctx: ["Licensed to thrill."])

    tui._show_about_menu(ctx)

    assert ctx.stack == []
    assert ctx.current_menu == ""
    footer = window.line(window.height - 2).strip()
    assert "Press Enter" in footer
