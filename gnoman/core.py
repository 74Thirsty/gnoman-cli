"""Core orchestration primitives for the modular GNOMAN CLI."""

from __future__ import annotations

import getpass
import hashlib
import hmac
import json
import logging
import os
import stat
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from dotenv import load_dotenv

try:  # pragma: no cover - depends on optional runtime providers
    from web3 import Web3
    from web3.providers.eth_tester import EthereumTesterProvider  # type: ignore
except Exception:  # pragma: no cover - Web3 is an install requirement
    Web3 = None  # type: ignore
    EthereumTesterProvider = None  # type: ignore

from eth_account import Account

try:  # pragma: no cover - optional dependency at runtime
    import keyring  # type: ignore
except Exception:  # pragma: no cover - keyring may not be installed
    keyring = None  # type: ignore


Account.enable_unaudited_hdwallet_features()

LOG_DIR = Path.home() / ".gnoman" / "logs"
LOG_FILE = LOG_DIR / "gnoman.log"
LEDGER_FILE = LOG_DIR / "gnoman_audit.jsonl"
ENV_PATH_DEFAULT = Path(".env")
SECRETS_INDEX = Path.home() / ".gnoman" / "secrets_index.json"
SERVICE_ENV_VAR = "GNOMAN_KEYRING_SERVICE"
HMAC_KEY_ENV = "AUDIT_HMAC_KEY"
DEFAULT_SERVICE = "gnoman"
RPC_ENV_KEY = "RPC_URL"
CHAIN_ID_ENV = "CHAIN_ID"
SAFE_ADDRESS_ENV = "GNOSIS_SAFE"
SIGNATURE_OK = "✅"
SIGNATURE_WARN = "⚠️"
SIGNATURE_ERR = "💥"


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _ensure_file_permissions(path: Path) -> None:
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except Exception:  # pragma: no cover - permission handling best effort
        return


class ForensicLedger:
    """Append-only forensic log with hash chaining and optional HMAC."""

    def __init__(self, path: Path = LEDGER_FILE, hmac_key_env: str = HMAC_KEY_ENV) -> None:
        self.path = path
        self.hmac_key_env = hmac_key_env
        _ensure_directory(self.path.parent)
        self.path.touch(exist_ok=True)
        _ensure_file_permissions(self.path)

    # -- internal helpers -------------------------------------------------
    def _load_last_hash(self) -> str:
        try:
            with self.path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                if size == 0:
                    return ""
                step = min(4096, size)
                position = size
                buffer = b""
                while position > 0:
                    position = max(0, position - step)
                    handle.seek(position)
                    chunk = handle.read(min(step, position + step))
                    buffer = chunk + buffer
                    if b"\n" in buffer:
                        break
                line = buffer.splitlines()[-1]
            payload = json.loads(line.decode("utf-8"))
            return str(payload.get("hash", ""))
        except Exception:
            return ""

    def _hmac_key(self) -> Optional[bytes]:
        service = os.getenv(SERVICE_ENV_VAR, DEFAULT_SERVICE)
        secret: Optional[str] = None
        if keyring is not None:
            try:
                secret = keyring.get_password(service, self.hmac_key_env)
            except Exception:
                secret = None
        if not secret:
            secret = os.getenv(self.hmac_key_env)
        return secret.encode("utf-8") if secret else None

    def _signature(self, ok: bool, severity: str) -> str:
        if not ok:
            return SIGNATURE_ERR
        if severity.upper() in {"WARNING", "WARN"}:
            return SIGNATURE_WARN
        return SIGNATURE_OK

    def log(
        self,
        action: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
        ok: bool = True,
        severity: str = "INFO",
    ) -> Dict[str, Any]:
        """Append a forensic record and return the serialised payload."""

        record = {
            "ts": time.time(),
            "action": action,
            "params": params or {},
            "result": result or {},
            "ok": bool(ok),
            "severity": severity.upper(),
            "signature": self._signature(ok, severity),
        }
        prev_hash = self._load_last_hash()
        envelope = {"prev": prev_hash, **record}
        digest_input = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
        record_hash = hashlib.sha256(digest_input).hexdigest()
        envelope["hash"] = record_hash
        hmac_key = self._hmac_key()
        if hmac_key:
            hmac_input = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
            envelope["hmac"] = hmac.new(hmac_key, hmac_input, hashlib.sha256).hexdigest()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(envelope, ensure_ascii=False) + "\n")
        return envelope


class EnvStore:
    """Handle flat key/value persistence in a ``.env`` file."""

    def __init__(self, path: Path = ENV_PATH_DEFAULT) -> None:
        self.path = path
        self._cache: Optional[Dict[str, str]] = None
        load_dotenv(self.path, override=False)

    def _load(self) -> Dict[str, str]:
        if self._cache is not None:
            return self._cache
        if not self.path.exists():
            self._cache = {}
            return self._cache
        values: Dict[str, str] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line or line.strip().startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
        self._cache = values
        return values

    def _write(self) -> None:
        values = self._load()
        lines = [f"{key}={value}" for key, value in sorted(values.items())]
        if lines:
            content = "\n".join(lines) + "\n"
        else:
            content = ""
        self.path.write_text(content, encoding="utf-8")
        _ensure_file_permissions(self.path)

    def get(self, key: str) -> Optional[str]:
        return self._load().get(key)

    def set(self, key: str, value: str) -> None:
        values = self._load()
        values[key] = value
        self._write()

    def remove(self, key: str) -> None:
        values = self._load()
        if key in values:
            del values[key]
            self._write()

    def keys(self) -> Iterable[str]:
        return list(self._load().keys())

    def snapshot(self) -> Dict[str, str]:
        return self._load().copy()


class SecretStore:
    """Centralised secret resolution with keyring-first semantics."""

    def __init__(
        self,
        ledger: ForensicLedger,
        env_store: EnvStore,
        *,
        service_name: Optional[str] = None,
        backend: Optional[Any] = None,
        index_path: Path = SECRETS_INDEX,
    ) -> None:
        self.ledger = ledger
        self.env_store = env_store
        self.service_name = service_name or os.getenv(SERVICE_ENV_VAR, DEFAULT_SERVICE)
        self.backend = backend if backend is not None else keyring
        self.index_path = index_path
        _ensure_directory(self.index_path.parent)
        if not self.index_path.exists():
            self.index_path.write_text("{}", encoding="utf-8")
        self._index_cache: Optional[Dict[str, Any]] = None

    # -- index helpers ----------------------------------------------------
    def _load_index(self) -> Dict[str, Any]:
        if self._index_cache is not None:
            return self._index_cache
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                self._index_cache = payload
            else:
                self._index_cache = {}
        except Exception:
            self._index_cache = {}
        return self._index_cache

    def _write_index(self, data: Dict[str, Any]) -> None:
        self.index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._index_cache = data

    def _touch_index(self, key: str, source: str) -> None:
        index = self._load_index()
        entry = index.setdefault(key, {
            "sources": [],
            "created_at": time.time(),
            "updated_at": time.time(),
        })
        if source not in entry["sources"]:
            entry["sources"].append(source)
        entry["updated_at"] = time.time()
        entry["last_access"] = time.time()
        self._write_index(index)

    def _remove_index(self, key: str) -> None:
        index = self._load_index()
        if key in index:
            index.pop(key)
            self._write_index(index)

    # -- helpers ----------------------------------------------------------
    def _preview(self, value: str) -> str:
        if len(value) <= 4:
            return "*" * len(value)
        return value[:2] + "*" * (len(value) - 4) + value[-2:]

    def _from_keyring(self, key: str) -> Optional[str]:
        if self.backend is None:
            return None
        try:
            return self.backend.get_password(self.service_name, key)
        except Exception:
            return None

    def _set_keyring(self, key: str, value: str) -> None:
        if self.backend is None:
            return
        try:
            self.backend.set_password(self.service_name, key, value)
        except Exception:
            pass

    def _delete_keyring(self, key: str) -> None:
        if self.backend is None:
            return
        try:
            self.backend.delete_password(self.service_name, key)
        except Exception:
            pass

    # -- public API -------------------------------------------------------
    def get(
        self,
        key: str,
        *,
        prompt_text: Optional[str] = None,
        allow_prompt: bool = True,
        sensitive: bool = True,
        default: Optional[str] = None,
    ) -> Optional[str]:
        value = self._from_keyring(key)
        if value:
            self.ledger.log(
                "secret_get",
                params={"key": key, "source": "keyring"},
                result={"preview": self._preview(value)},
            )
            self._touch_index(key, "keyring")
            return value
        env_value = self.env_store.get(key)
        if env_value is not None:
            self.ledger.log(
                "secret_get",
                params={"key": key, "source": "env"},
                result={"preview": self._preview(env_value)},
            )
            self._touch_index(key, "env")
            return env_value
        if allow_prompt and prompt_text:
            prompt = getpass.getpass if sensitive else input
            entered = prompt(prompt_text).strip()
            if entered:
                self._set_keyring(key, entered)
                self.env_store.set(key, entered)
                self.ledger.log(
                    "secret_prompt",
                    params={"key": key},
                    result={"source": "prompt"},
                )
                self._touch_index(key, "prompt")
                return entered
        if default is not None:
            return default
        self.ledger.log(
            "secret_missing",
            params={"key": key},
            ok=False,
            severity="WARNING",
        )
        return None

    def require(
        self,
        key: str,
        *,
        prompt_text: Optional[str] = None,
        sensitive: bool = True,
    ) -> str:
        value = self.get(key, prompt_text=prompt_text, allow_prompt=prompt_text is not None, sensitive=sensitive)
        if value is None:
            raise RuntimeError(f"missing required secret {key}")
        return value

    def set(self, key: str, value: str, *, persist_env: bool = True) -> None:
        value = value.strip()
        if not value:
            raise ValueError("secret value must not be empty")
        self._set_keyring(key, value)
        if persist_env:
            self.env_store.set(key, value)
        self._touch_index(key, "keyring")
        if persist_env:
            self._touch_index(key, "env")
        self.ledger.log(
            "secret_set",
            params={"key": key, "persist_env": persist_env},
            result={"preview": self._preview(value)},
        )

    def delete(self, key: str) -> None:
        self._delete_keyring(key)
        self.env_store.remove(key)
        self._remove_index(key)
        self.ledger.log("secret_delete", params={"key": key})

    def snapshot(self) -> Dict[str, Dict[str, Optional[str]]]:
        index = self._load_index()
        snapshot: Dict[str, Dict[str, Optional[str]]] = {}
        for key in sorted(set(list(index.keys()) + list(self.env_store.keys()))):
            sources: Dict[str, Optional[str]] = {}
            value_keyring = self._from_keyring(key)
            if value_keyring is not None:
                sources["keyring"] = value_keyring
            env_value = self.env_store.get(key)
            if env_value is not None:
                sources["env"] = env_value
            snapshot[key] = sources
        return snapshot

    def keys(self) -> Iterable[str]:
        snapshot = self.snapshot()
        return list(snapshot.keys())

    def metadata(self, key: str) -> Dict[str, Any]:
        index = self._load_index()
        if key not in index:
            return {}
        entry = index[key].copy()
        entry.pop("sources", None)
        return entry


@dataclass
class AppContext:
    """Singleton-style container exposing core subsystems."""

    ledger: ForensicLedger
    env_store: EnvStore
    secrets: SecretStore
    logger: logging.Logger
    _web3: Optional[Any] = None

    def get_web3(self, *, auto_connect: bool = True) -> Any:
        if self._web3 is None and auto_connect:
            self._web3 = self._connect_web3()
        return self._web3

    def _connect_web3(self) -> Any:
        if Web3 is None:
            raise RuntimeError("web3 provider is unavailable")
        rpc = self.secrets.get(RPC_ENV_KEY, allow_prompt=False)
        if rpc:
            provider = Web3.HTTPProvider(rpc)
            w3 = Web3(provider)
            try:
                if w3.is_connected():
                    chain_id = os.getenv(CHAIN_ID_ENV)
                    self.ledger.log(
                        "web3_connect",
                        params={"rpc": rpc},
                        result={"chain_id": chain_id},
                    )
                    return w3
            except Exception as exc:
                self.ledger.log(
                    "web3_connect",
                    params={"rpc": rpc},
                    ok=False,
                    severity="WARNING",
                    result={"error": str(exc)},
                )
        if EthereumTesterProvider is not None:
            tester = Web3(EthereumTesterProvider())
            self.ledger.log(
                "web3_connect",
                params={"rpc": "tester"},
                result={"mode": "ethereum-tester"},
            )
            return tester
        raise RuntimeError("unable to connect to any web3 provider")


_CONTEXT: Optional[AppContext] = None


def _configure_logger() -> logging.Logger:
    logger = logging.getLogger("gnoman")
    if logger.handlers:
        return logger
    _ensure_directory(LOG_DIR)
    formatter = logging.Formatter("%(asctime)s - gnoman - %(levelname)s - %(message)s")
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.info("%s Logger initialised", SIGNATURE_OK)
    return logger


def initialise_context(service_name: Optional[str] = None) -> AppContext:
    global _CONTEXT
    ledger = ForensicLedger()
    env_store = EnvStore()
    secrets = SecretStore(ledger, env_store, service_name=service_name)
    logger = _configure_logger()
    _CONTEXT = AppContext(ledger=ledger, env_store=env_store, secrets=secrets, logger=logger)
    return _CONTEXT


def get_context() -> AppContext:
    if _CONTEXT is None:
        return initialise_context()
    return _CONTEXT


def shutdown() -> None:
    context = get_context()
    context.logger.info("%s GNOMAN shutdown", SIGNATURE_OK)
    logging.shutdown()
