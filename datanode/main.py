from __future__ import annotations

import os
import threading
import time
from typing import Dict

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from datanode.storage import BlockStorage

NODE_ID = os.getenv("NODE_ID", "dn-local")
NODE_PORT = int(os.getenv("NODE_PORT", "8001"))
STORAGE_PATH = os.getenv("STORAGE_PATH", "./runtime/datanode-local")
NAMENODE_URL = os.getenv("NAMENODE_URL", "http://localhost:8000").rstrip("/")
BASE_URL = os.getenv("BASE_URL", f"http://localhost:{NODE_PORT}").rstrip("/")
CLIENT_URL = os.getenv("CLIENT_URL", f"http://localhost:{NODE_PORT}").rstrip("/")

app = FastAPI(
    title=f"DFS-Bloques DataNode {NODE_ID}",
    description="Nodo de almacenamiento físico de bloques para DFS-Bloques.",
    version="1.0.0",
)

storage = BlockStorage(STORAGE_PATH)


def register_with_namenode() -> None:
    payload = {"node_id": NODE_ID, "base_url": BASE_URL, "client_url": CLIENT_URL}
    for attempt in range(1, 21):
        try:
            resp = requests.post(f"{NAMENODE_URL}/datanodes/register", json=payload, timeout=3)
            if resp.ok:
                print(f"[{NODE_ID}] Registrado en NameNode: {NAMENODE_URL}")
                return
            print(f"[{NODE_ID}] Error registrando en NameNode: {resp.status_code} {resp.text}")
        except requests.RequestException as exc:
            print(f"[{NODE_ID}] NameNode no disponible todavía. Intento {attempt}/20. Error: {exc}")
        time.sleep(2)
    print(f"[{NODE_ID}] No se logró registrar automáticamente en NameNode.")


@app.on_event("startup")
def on_startup() -> None:
    thread = threading.Thread(target=register_with_namenode, daemon=True)
    thread.start()


@app.get("/health")
def health() -> Dict:
    return {
        "service": "datanode",
        "node_id": NODE_ID,
        "status": "ok",
        "storage_path": STORAGE_PATH,
        "blocks_count": len(storage.list_blocks()),
        "base_url": BASE_URL,
        "client_url": CLIENT_URL,
    }


@app.post("/blocks/{block_id}")
async def put_block(block_id: str, request: Request) -> Dict:
    data = await request.body()
    if data is None:
        raise HTTPException(status_code=400, detail="El cuerpo de la petición no contiene datos.")
    metadata = storage.put_block(block_id, data)
    return {"message": "Bloque almacenado correctamente.", "node_id": NODE_ID, "block": metadata}


@app.get("/blocks/{block_id}")
def get_block(block_id: str) -> FileResponse:
    path = storage.get_block_path(block_id)
    if not path:
        raise HTTPException(status_code=404, detail="Bloque no encontrado en este DataNode.")
    meta = storage.get_block_metadata(block_id) or {}
    headers = {
        "X-DFS-Node-Id": NODE_ID,
        "X-DFS-Block-Id": block_id,
    }
    if meta.get("checksum"):
        headers["X-DFS-Block-Checksum"] = meta["checksum"]
    return FileResponse(path, media_type="application/octet-stream", filename=path.name, headers=headers)


@app.delete("/blocks/{block_id}")
def delete_block(block_id: str) -> Dict:
    deleted = storage.delete_block(block_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Bloque no encontrado en este DataNode.")
    return {"message": "Bloque eliminado correctamente.", "node_id": NODE_ID, "block_id": block_id}


@app.get("/blocks")
def list_blocks() -> Dict:
    blocks = storage.list_blocks()
    return {"node_id": NODE_ID, "count": len(blocks), "blocks": blocks}
