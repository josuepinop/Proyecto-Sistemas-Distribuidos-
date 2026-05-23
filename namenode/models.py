from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    token: str
    username: str
    message: str


class RegisterUserRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class DataNodeRegisterRequest(BaseModel):
    node_id: str = Field(min_length=1)
    base_url: str = Field(min_length=1, description="URL interna usada por el NameNode dentro de Docker o red privada")
    client_url: str = Field(min_length=1, description="URL que el NameNode devuelve al cliente CLI")


class PutRequest(BaseModel):
    filename: str = Field(min_length=1)
    size: int = Field(ge=0)
    block_size: int = Field(gt=0)
    total_blocks: int = Field(ge=0)
    file_checksum: Optional[str] = None


class ReplicaAssignment(BaseModel):
    node_id: str
    client_url: str


class BlockAssignment(BaseModel):
    block_id: str
    order: int
    replicas: List[ReplicaAssignment]


class PutResponse(BaseModel):
    upload_id: str
    filename: str
    block_size: int
    total_blocks: int
    replication_factor: int
    assignments: List[BlockAssignment]


class CommittedBlock(BaseModel):
    block_id: str
    order: int
    size: int
    checksum: str
    locations: List[str] = Field(description="Lista de node_id donde el bloque quedó confirmado")


class CommitRequest(BaseModel):
    upload_id: str
    filename: str
    size: int
    block_size: int
    total_blocks: int
    file_checksum: Optional[str] = None
    blocks: List[CommittedBlock]


class DirectoryRequest(BaseModel):
    path: str = Field(min_length=1)
