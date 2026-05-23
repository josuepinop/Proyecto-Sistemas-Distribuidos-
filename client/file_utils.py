from __future__ import annotations

import math
from pathlib import Path
from typing import Iterator, Tuple


def iter_file_blocks(path: str | Path, block_size: int) -> Iterator[Tuple[int, bytes]]:
    with open(path, "rb") as f:
        order = 0
        while True:
            data = f.read(block_size)
            if not data:
                break
            yield order, data
            order += 1


def total_blocks_for_size(size: int, block_size: int) -> int:
    if size == 0:
        return 0
    return int(math.ceil(size / block_size))
