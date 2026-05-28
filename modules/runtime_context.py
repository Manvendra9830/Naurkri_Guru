from __future__ import annotations

from datetime import datetime
from uuid import uuid4


_CURRENT_RUNTIME_BATCH_ID: str | None = None


def generate_runtime_batch_id(prefix: str = "run") -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}_{uuid4().hex[:8]}"


def set_current_runtime_batch_id(runtime_batch_id: str | None = None) -> str:
    global _CURRENT_RUNTIME_BATCH_ID
    _CURRENT_RUNTIME_BATCH_ID = runtime_batch_id or generate_runtime_batch_id()
    return _CURRENT_RUNTIME_BATCH_ID


def get_current_runtime_batch_id() -> str | None:
    return _CURRENT_RUNTIME_BATCH_ID
