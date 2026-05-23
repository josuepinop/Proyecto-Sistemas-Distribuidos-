from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Crear archivo binario de prueba para DFS-Bloques")
    parser.add_argument("--output", required=True, help="Ruta del archivo a crear")
    parser.add_argument("--size-mb", type=int, default=3, help="Tamaño en MB")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    size = args.size_mb * 1024 * 1024
    pattern = b"DFS-BLOQUES-UPB-2026\n"

    with output.open("wb") as f:
        written = 0
        while written < size:
            chunk = pattern[: min(len(pattern), size - written)]
            f.write(chunk)
            written += len(chunk)

    print(f"Archivo creado: {output} ({size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
