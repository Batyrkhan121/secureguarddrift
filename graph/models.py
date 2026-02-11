# graph/models.py
# Модели: Node, Edge, Snapshot

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


@dataclass(frozen=True)
class Node:
    """Узел графа — сервис или компонент."""
    name: str                            # например "order-svc"
    namespace: str = "default"
    node_type: str = "service"           # "service" | "database" | "gateway"


@dataclass(frozen=True)
class Edge:
    """Ребро графа — связь между сервисами."""
    source: str                          # имя source-сервиса
    destination: str                     # имя dest-сервиса
    request_count: int = 0
    error_count: int = 0
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0

    def edge_key(self) -> tuple[str, str]:
        """Возвращает ключ ребра (source, destination)."""
        return (self.source, self.destination)

    def error_rate(self) -> float:
        """Возвращает error_count / request_count (или 0.0)."""
        if self.request_count == 0:
            return 0.0
        return self.error_count / self.request_count


@dataclass
class Snapshot:
    """Снапшот графа за определённый временной интервал."""
    snapshot_id: str = field(default_factory=lambda: uuid4().hex)
    timestamp_start: datetime = field(default_factory=datetime.utcnow)
    timestamp_end: datetime = field(default_factory=datetime.utcnow)
    edges: list[Edge] = field(default_factory=list)
    nodes: list[Node] = field(default_factory=list)


if __name__ == "__main__":
    n = Node(name="order-svc", node_type="service")
    e = Edge(source="order-svc", destination="payments-db", request_count=100, error_count=5)
    s = Snapshot(edges=[e], nodes=[n])
    print(f"Node: {n}")
    print(f"Edge: {e}, key={e.edge_key()}, error_rate={e.error_rate():.2%}")
    print(f"Snapshot: id={s.snapshot_id[:12]}... nodes={len(s.nodes)} edges={len(s.edges)}")
