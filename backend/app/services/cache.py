"""DEMO_MODE response cache: Groq responses are stored on disk and,
when DEMO_MODE=true, served from disk so the demo works if the API is slow.

Responses are always written after a successful call, so running the seeded
clips once fills the cache.
"""

import hashlib
import json
import os
from pathlib import Path

from ..config import BACKEND_DIR

CACHE_DIR = BACKEND_DIR / "storage" / "cache"


def demo_mode() -> bool:
    return os.getenv("DEMO_MODE", "false").strip().lower() in ("1", "true", "yes")


def key_for(*parts: bytes | str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, bytes) else p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def _path(kind: str, key: str) -> Path:
    return CACHE_DIR / kind / f"{key}.json"


def get(kind: str, key: str) -> dict | None:
    if not demo_mode():
        return None
    p = _path(kind, key)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def put(kind: str, key: str, data: dict) -> None:
    p = _path(kind, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
