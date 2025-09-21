"""Resolve configured derivation paths and validate arbitrary overrides."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Dict, Optional


class DerivationError(RuntimeError):
    """Raised when derivation path resolution fails."""


@dataclass
class DerivationResolver:
    """Resolve named derivation templates to fully qualified paths."""

    config_path: Optional[Path] = None

    _PATH_RE = re.compile(r"^m(\/\d+'?)*$")

    def __post_init__(self) -> None:
        self._templates = self._load_config()

    # -- configuration -----------------------------------------------------
    def _load_config(self) -> Dict[str, str]:
        if self.config_path is not None:
            data = self.config_path.read_text(encoding="utf-8")
        else:
            try:
                data = resources.files("gnoman.wallet_config").joinpath("derivations.json").read_text(encoding="utf-8")
            except FileNotFoundError as exc:  # pragma: no cover - packaging issue
                raise DerivationError("wallet derivation config missing") from exc
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as exc:
            raise DerivationError("invalid derivations configuration") from exc
        if not isinstance(payload, dict):
            raise DerivationError("derivations configuration must be an object")
        return {str(key): str(value) for key, value in payload.items()}

    # -- accessors ---------------------------------------------------------
    @property
    def templates(self) -> Dict[str, str]:
        return self._templates.copy()

    def available_paths(self) -> Dict[str, str]:
        return self.templates

    # -- public API --------------------------------------------------------
    def resolve(self, identifier: str, index: int) -> str:
        """Resolve ``identifier`` into a derivation path for ``index``.

        ``identifier`` can be a key from the configuration map or an explicit
        derivation string such as ``m/44'/60'/0'/0/0``. ``index`` is injected
        by replacing ``{index}`` tokens or, when the template ends with a slash,
        appended as the final segment.
        """

        template = self._templates.get(identifier, identifier)
        if not isinstance(template, str):
            raise DerivationError(f"invalid derivation template for {identifier}")
        path = self._materialise(template, index)
        if not self._PATH_RE.fullmatch(path):
            raise DerivationError(f"invalid derivation path produced: {path}")
        return path

    # -- helpers -----------------------------------------------------------
    def _materialise(self, template: str, index: int) -> str:
        if "{index}" in template:
            path = template.replace("{index}", str(index))
        elif template.endswith("/"):
            path = f"{template}{index}"
        elif template.count("/") == 0:
            # bare index-less template (e.g. "m/44'/60'/0'/0") -> append index
            path = f"{template}/{index}"
        else:
            path = template
        if "{" in path or "}" in path:
            raise DerivationError(f"unresolved placeholder in derivation path: {template}")
        return path
