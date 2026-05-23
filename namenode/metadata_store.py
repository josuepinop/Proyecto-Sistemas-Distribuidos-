from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from namenode.auth import AuthService


class MetadataStore:
    """JSON-backed metadata store for the academic DFS prototype.

    This is intentionally small and transparent. It can be replaced by SQLite
    without changing the external API if the project grows.
    """

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if not self.path.exists():
            self._write(self._empty_state())

    @staticmethod
    def _empty_state() -> Dict[str, Any]:
        return {
            "users": {},
            "directories": {},
            "files": {},
            "pending_uploads": {},
            "datanodes": {},
            "events": [],
        }

    def _read(self) -> Dict[str, Any]:
        with self._lock:
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    state = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                state = self._empty_state()
            for key, default in self._empty_state().items():
                state.setdefault(key, default)
            return state

    def _write(self, state: Dict[str, Any]) -> None:
        with self._lock:
            tmp = self.path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)

    def log_event(self, event_type: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        state = self._read()
        state["events"].append({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "type": event_type,
            "message": message,
            "details": details or {},
        })
        state["events"] = state["events"][-200:]
        self._write(state)

    def ensure_user(self, username: str, password: str) -> None:
        state = self._read()
        if username not in state["users"]:
            state["users"][username] = {
                "username": username,
                "password_hash": AuthService.hash_password(password),
                "created_at": time.time(),
            }
            state["directories"].setdefault(username, ["/"])
            state["files"].setdefault(username, {})
            self._write(state)
            self.log_event("USER_CREATED", f"Usuario inicial/registrado creado: {username}")

    def create_user(self, username: str, password: str) -> bool:
        state = self._read()
        if username in state["users"]:
            return False
        state["users"][username] = {
            "username": username,
            "password_hash": AuthService.hash_password(password),
            "created_at": time.time(),
        }
        state["directories"].setdefault(username, ["/"])
        state["files"].setdefault(username, {})
        self._write(state)
        self.log_event("USER_CREATED", f"Usuario creado: {username}")
        return True

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        return self._read()["users"].get(username)

    def register_datanode(self, node_id: str, base_url: str, client_url: str) -> Dict[str, Any]:
        state = self._read()
        node = {
            "node_id": node_id,
            "base_url": base_url.rstrip("/"),
            "client_url": client_url.rstrip("/"),
            "status": "active",
            "last_seen": time.time(),
        }
        state["datanodes"][node_id] = node
        self._write(state)
        self.log_event("DATANODE_REGISTERED", f"DataNode registrado: {node_id}", node)
        return node

    def update_datanode_status(self, node_id: str, status: str) -> None:
        state = self._read()
        if node_id in state["datanodes"]:
            state["datanodes"][node_id]["status"] = status
            state["datanodes"][node_id]["last_seen"] = time.time()
            self._write(state)

    def list_datanodes(self) -> List[Dict[str, Any]]:
        return list(self._read()["datanodes"].values())

    def active_datanodes(self) -> List[Dict[str, Any]]:
        return [n for n in self.list_datanodes() if n.get("status") == "active"]

    def save_pending_upload(self, upload_id: str, payload: Dict[str, Any]) -> None:
        state = self._read()
        state["pending_uploads"][upload_id] = payload
        self._write(state)
        self.log_event("UPLOAD_PENDING", f"Carga pendiente registrada: {upload_id}", {"filename": payload.get("filename")})

    def get_pending_upload(self, upload_id: str) -> Optional[Dict[str, Any]]:
        return self._read()["pending_uploads"].get(upload_id)

    def commit_file(self, owner: str, upload_id: str, file_metadata: Dict[str, Any]) -> None:
        state = self._read()
        state["files"].setdefault(owner, {})
        state["files"][owner][file_metadata["filename"]] = file_metadata
        state["pending_uploads"].pop(upload_id, None)
        self._write(state)
        self.log_event("FILE_COMMITTED", f"Archivo confirmado: {file_metadata['filename']}", {"owner": owner})

    def list_files(self, owner: str) -> List[Dict[str, Any]]:
        files = self._read()["files"].get(owner, {})
        return list(files.values())

    def get_file(self, owner: str, filename: str) -> Optional[Dict[str, Any]]:
        return self._read()["files"].get(owner, {}).get(filename)

    def delete_file_metadata(self, owner: str, filename: str) -> Optional[Dict[str, Any]]:
        state = self._read()
        file_metadata = state["files"].get(owner, {}).pop(filename, None)
        self._write(state)
        if file_metadata:
            self.log_event("FILE_DELETED", f"Metadatos eliminados: {filename}", {"owner": owner})
        return file_metadata

    def create_directory(self, owner: str, path: str) -> bool:
        normalized = self._normalize_dir(path)
        state = self._read()
        dirs = state["directories"].setdefault(owner, ["/"])
        if normalized in dirs:
            return False
        dirs.append(normalized)
        dirs.sort()
        self._write(state)
        self.log_event("DIRECTORY_CREATED", f"Directorio creado: {normalized}", {"owner": owner})
        return True

    def delete_directory(self, owner: str, path: str) -> bool:
        normalized = self._normalize_dir(path)
        if normalized == "/":
            return False
        state = self._read()
        dirs = state["directories"].setdefault(owner, ["/"])
        # Evitar borrar si contiene archivos o subdirectorios.
        prefix = normalized.rstrip("/") + "/"
        has_subdirs = any(d.startswith(prefix) for d in dirs if d != normalized)
        has_files = any(f.startswith(prefix.lstrip("/")) for f in state["files"].get(owner, {}))
        if has_subdirs or has_files or normalized not in dirs:
            return False
        dirs.remove(normalized)
        self._write(state)
        self.log_event("DIRECTORY_DELETED", f"Directorio eliminado: {normalized}", {"owner": owner})
        return True

    def list_directories(self, owner: str) -> List[str]:
        return self._read()["directories"].get(owner, ["/"])

    @staticmethod
    def _normalize_dir(path: str) -> str:
        path = path.strip().replace("\\", "/")
        if not path.startswith("/"):
            path = "/" + path
        while "//" in path:
            path = path.replace("//", "/")
        if len(path) > 1:
            path = path.rstrip("/")
        return path
