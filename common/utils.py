from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Dict


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def sanitize_block_id(block_id: str) -> str:
    """Return a safe file name for a block identifier.

    The DFS generates IDs with letters, numbers, underscore and dash.
    This function prevents path traversal if a malformed ID reaches the API.
    """
    block_id = block_id.strip()
    block_id = block_id.replace("/", "_").replace("\\", "_")
    return re.sub(r"[^A-Za-z0-9_.-]", "_", block_id)


def load_env_file(path: str | Path = ".env") -> Dict[str, str]:
    """Small .env loader without adding python-dotenv as dependency.

    Existing environment variables are not overwritten.
    """
    path = Path(path)
    loaded: Dict[str, str] = {}
    if not path.exists():
        return loaded
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded
