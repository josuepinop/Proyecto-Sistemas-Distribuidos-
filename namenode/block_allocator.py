from __future__ import annotations

from typing import Dict, List


def round_robin_assignments(
    *,
    owner: str,
    upload_id: str,
    total_blocks: int,
    datanodes: List[Dict],
    replication_factor: int,
) -> List[Dict]:
    """Assign each block to N distinct active DataNodes using round-robin."""
    if replication_factor <= 0:
        raise ValueError("El factor de replicación debe ser mayor que cero.")
    if len(datanodes) < replication_factor:
        raise ValueError(
            f"DataNodes activos insuficientes: {len(datanodes)} disponibles, "
            f"{replication_factor} requeridos."
        )

    assignments: List[Dict] = []
    n = len(datanodes)
    safe_owner = owner.replace("/", "_").replace("\\", "_")
    for i in range(total_blocks):
        replicas = []
        used = set()
        r = 0
        while len(replicas) < replication_factor:
            node = datanodes[(i + r) % n]
            r += 1
            if node["node_id"] in used:
                continue
            used.add(node["node_id"])
            replicas.append({
                "node_id": node["node_id"],
                "client_url": node["client_url"],
            })
        assignments.append({
            "block_id": f"{safe_owner}_{upload_id}_block_{i}",
            "order": i,
            "replicas": replicas,
        })
    return assignments
