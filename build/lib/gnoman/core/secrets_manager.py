"""Secret and keyring management primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from ..utils import keyring_backend
from .log_manager import log_event


@dataclass
class SecretRecord:
    """Materialised representation of a stored secret."""

    service: str
    username: str
    secret: Optional[str] = None
    metadata: Optional[Dict[str, object]] = None


class SecretsManager:
    """High level façade around the platform specific keyring backends."""

    def list(self, *, namespace: Optional[str] = None, include_values: bool = False) -> List[SecretRecord]:
        entries = keyring_backend.list_all_entries()
        result: List[SecretRecord] = []
        for entry in entries:
            if namespace and not entry.service.startswith(namespace):
                continue
            if include_values:
                hydrated = keyring_backend.get_entry(entry.service, entry.username)
                if hydrated is None:
                    continue
                result.append(
                    SecretRecord(
                        service=hydrated.service,
                        username=hydrated.username,
                        secret=hydrated.secret,
                        metadata=hydrated.metadata,
                    )
                )
            else:
                result.append(
                    SecretRecord(
                        service=entry.service,
                        username=entry.username,
                        metadata=entry.metadata,
                    )
                )
        return result

    def add(self, *, service: str, username: str, secret: str) -> None:
        keyring_backend.set_entry(service, username, secret)
        log_event("secret-add", service=service, username=username)

    def delete(self, *, service: str, username: str) -> None:
        keyring_backend.delete_entry(service, username)
        log_event("secret-delete", service=service, username=username)

    def rotate(self, *, services: Optional[Iterable[str]] = None, length: int = 32) -> int:
        rotated = keyring_backend.rotate_entries(services=services, length=length)
        log_event("secret-rotate", services=list(services or []), count=rotated)
        return rotated


__all__ = ["SecretRecord", "SecretsManager"]
