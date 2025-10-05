from __future__ import annotations

import pytest

pytest.importorskip("rich")
pytest.importorskip("textual")

from gnoman.ui.main import GNOMANMain


def test_ui_initialises() -> None:
    app = GNOMANMain()
    # Ensure compose() yields the expected structure without raising
    components = list(app.compose())
    assert components
