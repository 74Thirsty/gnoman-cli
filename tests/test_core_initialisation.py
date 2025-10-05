"""Tests for interactive initialisation helpers in :mod:`gnoman.core`."""

import importlib
import sys
from types import ModuleType, SimpleNamespace


def _import_core() -> ModuleType:
    """Return the real :mod:`gnoman.core` module, reloading if it was stubbed."""

    module = sys.modules.get("gnoman.core")
    if isinstance(module, ModuleType):
        return module
    sys.modules.pop("gnoman.core", None)
    return importlib.import_module("gnoman.core")

def test_service_name_uses_environment(monkeypatch) -> None:
    module = _import_core()

    monkeypatch.setenv(module.SERVICE_NAME_ENV, "custom-service")
    monkeypatch.setattr(module, "_SERVICE_NAME", None, raising=False)

    assert module._service_name() == "custom-service"


def test_service_name_defaults_without_tty(monkeypatch) -> None:
    module = _import_core()

    monkeypatch.delenv(module.SERVICE_NAME_ENV, raising=False)
    monkeypatch.setattr(module, "_SERVICE_NAME", None, raising=False)
    fake_stdin = SimpleNamespace(isatty=lambda: False)
    monkeypatch.setattr(module.sys, "stdin", fake_stdin)

    assert module._service_name() == module.DEFAULT_SERVICE_NAME


def test_web3_initialised_lazily(monkeypatch) -> None:
    module = _import_core()

    monkeypatch.setattr(module, "_WEB3", None, raising=False)
    sentinel = object()
    monkeypatch.setattr(module, "_init_web3", lambda: sentinel)

    assert module._get_web3() is sentinel
    assert module._WEB3 is sentinel
