from pathlib import Path

from client.file_utils import iter_file_blocks, total_blocks_for_size


def test_total_blocks_for_size():
    assert total_blocks_for_size(0, 1024) == 0
    assert total_blocks_for_size(1, 1024) == 1
    assert total_blocks_for_size(1024, 1024) == 1
    assert total_blocks_for_size(1025, 1024) == 2


def test_iter_file_blocks(tmp_path: Path):
    p = tmp_path / "a.bin"
    p.write_bytes(b"abcdef")
    blocks = list(iter_file_blocks(p, 2))
    assert blocks == [(0, b"ab"), (1, b"cd"), (2, b"ef")]
