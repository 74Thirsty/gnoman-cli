"""Helpers for loading ABI definitions bundled with the CLI."""

from __future__ import annotations

import json
import os
from importlib import resources
from pathlib import Path
from typing import Any, Tuple

AbiType = Any


def _normalise_abi_payload(payload: Any) -> AbiType:
    """Extract the ABI array from a JSON payload.

    The bundled Safe ABI is stored as either a raw ABI array or a dictionary
    with an ``"abi"`` key. This helper accepts both structures.
    """

    if isinstance(payload, dict) and "abi" in payload:
        return payload["abi"]
    return payload


def _load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        raise FileNotFoundError(f"Unable to read ABI file at {path!s}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid ABI JSON payload at {path!s}") from exc


def load_safe_abi() -> Tuple[AbiType, str]:
    """Load the Gnosis Safe ABI, returning the ABI object and its source.

    ``GNOSIS_SAFE_ABI`` may be set to point at a custom JSON definition. When it
    is not provided, the packaged ``GnosisSafe.json`` resource is used instead.
    """

    env_override = os.getenv("GNOSIS_SAFE_ABI")
    if env_override:
        override_path = Path(env_override).expanduser()
        payload = _load_json(override_path)
        return _normalise_abi_payload(payload), str(override_path)

    resource = resources.files("gnoman.data").joinpath("GnosisSafe.json")
    with resource.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return _normalise_abi_payload(payload), str(resource)

