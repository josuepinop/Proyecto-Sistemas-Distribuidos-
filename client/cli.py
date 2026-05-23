from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Permite ejecutar desde la raíz con: python client/cli.py ...
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from client.dfs_client import DFSClient, DFSClientError  # noqa: E402
from common.utils import load_env_file  # noqa: E402


def print_json(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cliente CLI para DFS-Bloques")
    parser.add_argument("--namenode", default=None, help="URL del NameNode. Por defecto lee NAMENODE_URL o usa http://localhost:8000")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="Verificar estado del NameNode")

    login = sub.add_parser("login", help="Autenticarse en el DFS")
    login.add_argument("--user", required=True)
    login.add_argument("--password", required=True)

    register = sub.add_parser("register", help="Crear un usuario nuevo")
    register.add_argument("--user", required=True)
    register.add_argument("--password", required=True)

    sub.add_parser("datanodes", help="Listar DataNodes registrados")
    sub.add_parser("ls", help="Listar archivos y directorios del usuario autenticado")
    sub.add_parser("events", help="Ver últimos eventos del NameNode")

    put = sub.add_parser("put", help="Subir archivo al DFS")
    put.add_argument("local_path", help="Ruta del archivo local")
    put.add_argument("--name", default=None, help="Nombre lógico del archivo en el DFS")
    put.add_argument("--block-size-mb", type=int, default=int(os.getenv("BLOCK_SIZE_MB", "64")))

    get = sub.add_parser("get", help="Descargar archivo desde el DFS")
    get.add_argument("filename", help="Nombre lógico del archivo en el DFS")
    get.add_argument("--output", default=None, help="Ruta destino del archivo reconstruido")

    rm = sub.add_parser("rm", help="Eliminar archivo del DFS")
    rm.add_argument("filename")

    mkdir = sub.add_parser("mkdir", help="Crear directorio lógico")
    mkdir.add_argument("path")

    rmdir = sub.add_parser("rmdir", help="Eliminar directorio lógico vacío")
    rmdir.add_argument("path")

    return parser


def main() -> int:
    load_env_file(".env")
    parser = build_parser()
    args = parser.parse_args()
    client = DFSClient(namenode_url=args.namenode)

    try:
        if args.command == "health":
            print_json(client.health())
        elif args.command == "login":
            print_json(client.login(args.user, args.password))
        elif args.command == "register":
            print_json(client.register(args.user, args.password))
        elif args.command == "datanodes":
            print_json(client.datanodes())
        elif args.command == "ls":
            print_json(client.list_files())
        elif args.command == "events":
            print_json(client.events())
        elif args.command == "put":
            print_json(client.put(args.local_path, dfs_name=args.name, block_size_mb=args.block_size_mb))
        elif args.command == "get":
            print_json(client.get(args.filename, output=args.output))
        elif args.command == "rm":
            print_json(client.rm(args.filename))
        elif args.command == "mkdir":
            print_json(client.mkdir(args.path))
        elif args.command == "rmdir":
            print_json(client.rmdir(args.path))
        return 0
    except DFSClientError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Operación cancelada.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
