from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from common.utils import load_env_file, sha256_bytes, sha256_file
from client.file_utils import iter_file_blocks, total_blocks_for_size


class DFSClientError(Exception):
    pass


class DFSClient:
    def __init__(self, namenode_url: Optional[str] = None, session_path: str | Path = ".dfs_session.json") -> None:
        load_env_file(".env")
        self.namenode_url = (namenode_url or os.getenv("NAMENODE_URL", "http://localhost:8000")).rstrip("/")
        self.session_path = Path(session_path)
        self.timeout = float(os.getenv("REQUEST_TIMEOUT", "5"))
        self.token: Optional[str] = None
        self.username: Optional[str] = None
        self._load_session()

    def _load_session(self) -> None:
        if not self.session_path.exists():
            return
        try:
            data = json.loads(self.session_path.read_text(encoding="utf-8"))
            self.token = data.get("token")
            self.username = data.get("username")
        except json.JSONDecodeError:
            self.token = None
            self.username = None

    def _save_session(self) -> None:
        self.session_path.write_text(
            json.dumps({"token": self.token, "username": self.username, "namenode_url": self.namenode_url}, indent=2),
            encoding="utf-8",
        )

    def _headers(self) -> Dict[str, str]:
        if not self.token:
            raise DFSClientError("No hay sesión activa. Ejecuta primero: python client/cli.py login --user santiago --password 1234")
        return {"Authorization": f"Bearer {self.token}"}

    @staticmethod
    def _parse_response(resp: requests.Response) -> Dict[str, Any]:
        try:
            data = resp.json()
        except ValueError:
            data = {"raw": resp.text}
        if not resp.ok:
            detail = data.get("detail", data)
            raise DFSClientError(f"HTTP {resp.status_code}: {detail}")
        return data

    def health(self) -> Dict[str, Any]:
        resp = requests.get(f"{self.namenode_url}/health", timeout=self.timeout)
        return self._parse_response(resp)

    def login(self, username: str, password: str) -> Dict[str, Any]:
        resp = requests.post(
            f"{self.namenode_url}/auth/login",
            json={"username": username, "password": password},
            timeout=self.timeout,
        )
        data = self._parse_response(resp)
        self.token = data["token"]
        self.username = data["username"]
        self._save_session()
        return data

    def register(self, username: str, password: str) -> Dict[str, Any]:
        resp = requests.post(
            f"{self.namenode_url}/auth/register",
            json={"username": username, "password": password},
            timeout=self.timeout,
        )
        return self._parse_response(resp)

    def datanodes(self) -> Dict[str, Any]:
        resp = requests.get(f"{self.namenode_url}/datanodes", timeout=self.timeout)
        return self._parse_response(resp)

    def list_files(self) -> Dict[str, Any]:
        resp = requests.get(f"{self.namenode_url}/files", headers=self._headers(), timeout=self.timeout)
        return self._parse_response(resp)

    def mkdir(self, path: str) -> Dict[str, Any]:
        resp = requests.post(f"{self.namenode_url}/directories", headers=self._headers(), json={"path": path}, timeout=self.timeout)
        return self._parse_response(resp)

    def rmdir(self, path: str) -> Dict[str, Any]:
        clean = path.strip("/") or path
        resp = requests.delete(f"{self.namenode_url}/directories/{clean}", headers=self._headers(), timeout=self.timeout)
        return self._parse_response(resp)

    def put(self, local_path: str | Path, dfs_name: Optional[str] = None, block_size_mb: int = 64) -> Dict[str, Any]:
        path = Path(local_path)
        if not path.exists() or not path.is_file():
            raise DFSClientError(f"El archivo local no existe o no es un archivo: {path}")
        block_size = block_size_mb * 1024 * 1024
        size = path.stat().st_size
        total_blocks = total_blocks_for_size(size, block_size)
        filename = dfs_name or path.name
        file_checksum = sha256_file(path)

        put_req = {
            "filename": filename,
            "size": size,
            "block_size": block_size,
            "total_blocks": total_blocks,
            "file_checksum": file_checksum,
        }
        resp = requests.post(
            f"{self.namenode_url}/files/put-request",
            headers=self._headers(),
            json=put_req,
            timeout=self.timeout,
        )
        assignment_data = self._parse_response(resp)
        assignments = {item["order"]: item for item in assignment_data["assignments"]}

        committed_blocks: List[Dict[str, Any]] = []
        for order, content in iter_file_blocks(path, block_size):
            assignment = assignments[order]
            block_id = assignment["block_id"]
            block_checksum = sha256_bytes(content)
            locations: List[str] = []
            errors: List[str] = []

            for replica in assignment["replicas"]:
                node_id = replica["node_id"]
                url = f"{replica['client_url'].rstrip('/')}/blocks/{block_id}"
                try:
                    block_resp = requests.post(
                        url,
                        data=content,
                        headers={"Content-Type": "application/octet-stream", "X-DFS-Block-Checksum": block_checksum},
                        timeout=self.timeout,
                    )
                    if block_resp.ok:
                        locations.append(node_id)
                    else:
                        errors.append(f"{node_id}: HTTP {block_resp.status_code} {block_resp.text}")
                except requests.RequestException as exc:
                    errors.append(f"{node_id}: {exc}")

            if len(set(locations)) < assignment_data["replication_factor"]:
                raise DFSClientError(
                    f"No se pudo guardar el bloque {block_id} con el factor de replicación requerido. "
                    f"Ubicaciones confirmadas={locations}. Errores={errors}"
                )
            committed_blocks.append({
                "block_id": block_id,
                "order": order,
                "size": len(content),
                "checksum": block_checksum,
                "locations": locations,
            })

        commit_req = {
            "upload_id": assignment_data["upload_id"],
            "filename": filename,
            "size": size,
            "block_size": block_size,
            "total_blocks": total_blocks,
            "file_checksum": file_checksum,
            "blocks": committed_blocks,
        }
        resp = requests.post(
            f"{self.namenode_url}/files/commit",
            headers=self._headers(),
            json=commit_req,
            timeout=self.timeout,
        )
        commit_data = self._parse_response(resp)
        commit_data["local_file_checksum"] = file_checksum
        return commit_data

    def get(self, filename: str, output: Optional[str | Path] = None) -> Dict[str, Any]:
        resp = requests.get(
            f"{self.namenode_url}/files/{filename}/blocks",
            headers=self._headers(),
            timeout=self.timeout,
        )
        metadata = self._parse_response(resp)
        output_path = Path(output) if output else Path("downloads") / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        attempted: List[Dict[str, Any]] = []
        with output_path.open("wb") as out:
            for block in sorted(metadata["blocks"], key=lambda b: b["order"]):
                block_id = block["block_id"]
                expected_checksum = block.get("checksum")
                block_ok = False
                last_error = None
                for loc in block["locations"]:
                    node_id = loc["node_id"]
                    url = f"{loc['client_url'].rstrip('/')}/blocks/{block_id}"
                    try:
                        block_resp = requests.get(url, timeout=self.timeout)
                        attempted.append({"block_id": block_id, "node_id": node_id, "status": block_resp.status_code})
                        if not block_resp.ok:
                            last_error = f"{node_id}: HTTP {block_resp.status_code}"
                            continue
                        content = block_resp.content
                        actual_checksum = sha256_bytes(content)
                        if expected_checksum and actual_checksum != expected_checksum:
                            last_error = f"{node_id}: checksum inválido"
                            continue
                        out.write(content)
                        block_ok = True
                        break
                    except requests.RequestException as exc:
                        attempted.append({"block_id": block_id, "node_id": node_id, "error": str(exc)})
                        last_error = str(exc)
                if not block_ok:
                    raise DFSClientError(f"BLOCK_NOT_AVAILABLE: No se pudo recuperar {block_id}. Último error: {last_error}")

        recovered_checksum = sha256_file(output_path)
        expected_file_checksum = metadata.get("file_checksum")
        checksum_match = expected_file_checksum is None or recovered_checksum == expected_file_checksum
        if not checksum_match:
            raise DFSClientError(
                f"El archivo fue reconstruido, pero el hash no coincide. "
                f"Esperado={expected_file_checksum}, obtenido={recovered_checksum}"
            )
        return {
            "message": "Archivo descargado y reconstruido correctamente.",
            "filename": filename,
            "output": str(output_path),
            "sha256": recovered_checksum,
            "checksum_match": checksum_match,
            "attempted": attempted,
        }

    def rm(self, filename: str) -> Dict[str, Any]:
        resp = requests.delete(f"{self.namenode_url}/files/{filename}", headers=self._headers(), timeout=self.timeout)
        return self._parse_response(resp)

    def events(self) -> Dict[str, Any]:
        resp = requests.get(f"{self.namenode_url}/events", headers=self._headers(), timeout=self.timeout)
        return self._parse_response(resp)
