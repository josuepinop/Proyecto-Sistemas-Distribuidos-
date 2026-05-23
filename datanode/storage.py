from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from common.utils import sanitize_block_id, sha256_bytes


class BlockStorage:
    def __init__(self, storage_path: str) -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _block_path(self, block_id: str) -> Path:
        return self.storage_path / sanitize_block_id(block_id)

    def _meta_path(self, block_id: str) -> Path:
        return self.storage_path / f"{sanitize_block_id(block_id)}.meta.json"

    def put_block(self, block_id: str, data: bytes) -> Dict:
        block_path = self._block_path(block_id)
        checksum = sha256_bytes(data)
        block_path.write_bytes(data)
        metadata = {
            "block_id": block_id,
            "stored_name": block_path.name,
            "size": len(data),
            "checksum": checksum,
        }
        self._meta_path(block_id).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return metadata

    def get_block_path(self, block_id: str) -> Optional[Path]:
        block_path = self._block_path(block_id)
        if not block_path.exists() or not block_path.is_file():
            return None
        return block_path

    def get_block_metadata(self, block_id: str) -> Optional[Dict]:
        meta_path = self._meta_path(block_id)
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def delete_block(self, block_id: str) -> bool:
        deleted = False
        for path in [self._block_path(block_id), self._meta_path(block_id)]:
            if path.exists():
                path.unlink()
                deleted = True
        return deleted

    def list_blocks(self) -> List[Dict]:
        blocks: List[Dict] = []
        for path in sorted(self.storage_path.iterdir()):
            if path.name.endswith(".meta.json") or not path.is_file():
                continue
            meta = self.get_block_metadata(path.name)
            if meta:
                blocks.append(meta)
            else:
                blocks.append({"block_id": path.name, "stored_name": path.name, "size": path.stat().st_size})
        return blocks
