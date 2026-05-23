from __future__ import annotations

import os
import time
import uuid
from typing import Dict, List

import requests
from fastapi import Depends, FastAPI, Header, HTTPException, status

from namenode.auth import AuthService
from namenode.block_allocator import round_robin_assignments
from namenode.metadata_store import MetadataStore
from namenode.models import (
    CommitRequest,
    DataNodeRegisterRequest,
    DirectoryRequest,
    LoginRequest,
    LoginResponse,
    PutRequest,
    RegisterUserRequest,
)

METADATA_DB = os.getenv("METADATA_DB", "./runtime/namenode/metadata.json")
REPLICATION_FACTOR = int(os.getenv("REPLICATION_FACTOR", "2"))
DEFAULT_USERNAME = os.getenv("DEFAULT_USERNAME", "santiago")
DEFAULT_PASSWORD = os.getenv("DEFAULT_PASSWORD", "1234")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "5"))

app = FastAPI(
    title="DFS-Bloques NameNode",
    description="Servidor central de metadatos para un DFS académico por bloques.",
    version="1.0.0",
)

store = MetadataStore(METADATA_DB)
auth = AuthService()
store.ensure_user(DEFAULT_USERNAME, DEFAULT_PASSWORD)


def require_auth(authorization: str = Header(default="")) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token no enviado o formato inválido.")
    token = authorization.removeprefix("Bearer ").strip()
    username = auth.get_username(token)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o sesión expirada.")
    return username


def refresh_datanode_statuses() -> None:
    """Best-effort health check. Uses internal base_url, not client_url."""
    for node in store.list_datanodes():
        try:
            resp = requests.get(f"{node['base_url'].rstrip('/')}/health", timeout=REQUEST_TIMEOUT)
            if resp.ok:
                store.update_datanode_status(node["node_id"], "active")
            else:
                store.update_datanode_status(node["node_id"], "inactive")
        except requests.RequestException:
            store.update_datanode_status(node["node_id"], "inactive")


@app.get("/health")
def health() -> Dict:
    return {
        "service": "namenode",
        "status": "ok",
        "replication_factor": REPLICATION_FACTOR,
        "metadata_db": METADATA_DB,
    }


@app.post("/auth/register", status_code=201)
def register_user(payload: RegisterUserRequest) -> Dict:
    created = store.create_user(payload.username, payload.password)
    if not created:
        raise HTTPException(status_code=409, detail="El usuario ya existe.")
    return {"message": "Usuario creado correctamente.", "username": payload.username}


@app.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    user = store.get_user(payload.username)
    if not user or not AuthService.verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Usuario o contraseña inválidos.")
    token = auth.create_token(payload.username)
    return LoginResponse(token=token, username=payload.username, message="Login exitoso.")


@app.post("/datanodes/register")
def register_datanode(payload: DataNodeRegisterRequest) -> Dict:
    node = store.register_datanode(payload.node_id, payload.base_url, payload.client_url)
    return {"message": "DataNode registrado correctamente.", "datanode": node}


@app.get("/datanodes")
def list_datanodes(check_health: bool = True) -> Dict:
    if check_health:
        refresh_datanode_statuses()
    nodes = store.list_datanodes()
    return {"count": len(nodes), "datanodes": nodes}


@app.post("/files/put-request")
def put_request(payload: PutRequest, username: str = Depends(require_auth)) -> Dict:
    if payload.total_blocks == 0 and payload.size > 0:
        raise HTTPException(status_code=400, detail="total_blocks no puede ser 0 para un archivo con contenido.")
    if store.get_file(username, payload.filename):
        raise HTTPException(status_code=409, detail="Ya existe un archivo con ese nombre para el usuario.")

    refresh_datanode_statuses()
    active_nodes = store.active_datanodes()
    if len(active_nodes) < REPLICATION_FACTOR:
        raise HTTPException(
            status_code=503,
            detail=f"DataNodes activos insuficientes. Activos={len(active_nodes)}, requeridos={REPLICATION_FACTOR}.",
        )

    upload_id = uuid.uuid4().hex[:12]
    assignments = round_robin_assignments(
        owner=username,
        upload_id=upload_id,
        total_blocks=payload.total_blocks,
        datanodes=active_nodes,
        replication_factor=REPLICATION_FACTOR,
    )
    pending = {
        "upload_id": upload_id,
        "owner": username,
        "filename": payload.filename,
        "size": payload.size,
        "block_size": payload.block_size,
        "total_blocks": payload.total_blocks,
        "file_checksum": payload.file_checksum,
        "assignments": assignments,
        "created_at": time.time(),
    }
    store.save_pending_upload(upload_id, pending)
    return {
        "upload_id": upload_id,
        "filename": payload.filename,
        "block_size": payload.block_size,
        "total_blocks": payload.total_blocks,
        "replication_factor": REPLICATION_FACTOR,
        "assignments": assignments,
    }


@app.post("/files/commit")
def commit_file(payload: CommitRequest, username: str = Depends(require_auth)) -> Dict:
    pending = store.get_pending_upload(payload.upload_id)
    if not pending:
        raise HTTPException(status_code=404, detail="No existe una carga pendiente con ese upload_id.")
    if pending["owner"] != username:
        raise HTTPException(status_code=403, detail="El upload_id pertenece a otro usuario.")
    if pending["filename"] != payload.filename:
        raise HTTPException(status_code=400, detail="El nombre del archivo no coincide con la solicitud inicial.")
    if len(payload.blocks) != pending["total_blocks"]:
        raise HTTPException(status_code=400, detail="La cantidad de bloques confirmados no coincide con lo solicitado.")

    known_nodes = {n["node_id"]: n for n in store.list_datanodes()}
    file_blocks: List[Dict] = []
    for block in sorted(payload.blocks, key=lambda b: b.order):
        if len(set(block.locations)) < REPLICATION_FACTOR:
            raise HTTPException(
                status_code=400,
                detail=f"El bloque {block.block_id} no alcanzó el factor de replicación requerido.",
            )
        locations = []
        for node_id in block.locations:
            node = known_nodes.get(node_id)
            if not node:
                raise HTTPException(status_code=400, detail=f"DataNode desconocido en commit: {node_id}")
            locations.append({
                "node_id": node_id,
                "client_url": node["client_url"],
                "base_url": node["base_url"],
            })
        file_blocks.append({
            "block_id": block.block_id,
            "order": block.order,
            "size": block.size,
            "checksum": block.checksum,
            "locations": locations,
        })

    metadata = {
        "filename": payload.filename,
        "owner": username,
        "size": payload.size,
        "block_size": payload.block_size,
        "total_blocks": payload.total_blocks,
        "file_checksum": payload.file_checksum,
        "replication_factor": REPLICATION_FACTOR,
        "status": "available",
        "created_at": time.time(),
        "blocks": file_blocks,
    }
    store.commit_file(username, payload.upload_id, metadata)
    return {"message": "Archivo confirmado correctamente.", "file": metadata}


@app.get("/files")
def list_files(username: str = Depends(require_auth)) -> Dict:
    return {
        "owner": username,
        "directories": store.list_directories(username),
        "files": store.list_files(username),
    }


@app.get("/files/{filename}/blocks")
def get_file_blocks(filename: str, username: str = Depends(require_auth)) -> Dict:
    file_metadata = store.get_file(username, filename)
    if not file_metadata:
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    # No se devuelven base_url internas al cliente; solo URLs cliente.
    safe_blocks = []
    for block in sorted(file_metadata["blocks"], key=lambda b: b["order"]):
        safe_blocks.append({
            "block_id": block["block_id"],
            "order": block["order"],
            "size": block["size"],
            "checksum": block["checksum"],
            "locations": [
                {"node_id": loc["node_id"], "client_url": loc["client_url"]}
                for loc in block["locations"]
            ],
        })
    return {
        "filename": file_metadata["filename"],
        "owner": username,
        "size": file_metadata["size"],
        "block_size": file_metadata["block_size"],
        "total_blocks": file_metadata["total_blocks"],
        "file_checksum": file_metadata.get("file_checksum"),
        "blocks": safe_blocks,
    }


@app.delete("/files/{filename}")
def delete_file(filename: str, username: str = Depends(require_auth)) -> Dict:
    file_metadata = store.get_file(username, filename)
    if not file_metadata:
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    deleted_blocks = []
    failed_deletions = []
    for block in file_metadata["blocks"]:
        for loc in block["locations"]:
            try:
                resp = requests.delete(
                    f"{loc['base_url'].rstrip('/')}/blocks/{block['block_id']}",
                    timeout=REQUEST_TIMEOUT,
                )
                if resp.ok:
                    deleted_blocks.append({"block_id": block["block_id"], "node_id": loc["node_id"]})
                else:
                    failed_deletions.append({"block_id": block["block_id"], "node_id": loc["node_id"], "status": resp.status_code})
            except requests.RequestException as exc:
                failed_deletions.append({"block_id": block["block_id"], "node_id": loc["node_id"], "error": str(exc)})

    removed = store.delete_file_metadata(username, filename)
    return {
        "message": "Archivo eliminado de metadatos. Se intentó eliminar cada réplica física.",
        "file_removed": bool(removed),
        "deleted_blocks": deleted_blocks,
        "failed_deletions": failed_deletions,
    }


@app.post("/directories", status_code=201)
def create_directory(payload: DirectoryRequest, username: str = Depends(require_auth)) -> Dict:
    created = store.create_directory(username, payload.path)
    if not created:
        raise HTTPException(status_code=409, detail="El directorio ya existe o no pudo crearse.")
    return {"message": "Directorio creado correctamente.", "path": payload.path}


@app.delete("/directories/{path:path}")
def delete_directory(path: str, username: str = Depends(require_auth)) -> Dict:
    deleted = store.delete_directory(username, path)
    if not deleted:
        raise HTTPException(status_code=400, detail="No se pudo eliminar el directorio. Puede no existir, ser raíz o no estar vacío.")
    return {"message": "Directorio eliminado correctamente.", "path": path}


@app.get("/events")
def events(username: str = Depends(require_auth)) -> Dict:
    # Endpoint útil para evidencias. En una versión real se restringiría por rol.
    state = store._read()  # noqa: SLF001 - aceptado para prototipo académico.
    return {"events": state.get("events", [])[-100:]}
