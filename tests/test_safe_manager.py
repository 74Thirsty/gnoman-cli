from __future__ import annotations

import pytest

from gnoman.core.safe_manager import SafeManager


def test_safe_manager_dependency_guard() -> None:
    pytest.importorskip("gnosis.safe")
    manager = SafeManager(rpc_url="http://localhost:0")
    with pytest.raises(Exception):
        manager.deploy_safe(owners=["0x" + "0" * 40], threshold=1)
