from __future__ import annotations

import pytest

pytest.importorskip("prompt_toolkit")
pytest.importorskip("rich")

from gnoman.ui import TerminalUI


def test_terminal_ui_menu_labels() -> None:
    ui = TerminalUI()
    labels = ui.main_menu_labels
    assert "Secrets Vault" in labels
    assert "Wallet Hangar" in labels
    assert labels[-1] == "Quit"
