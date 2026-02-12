"""Root cause analysis using graph-based error propagation."""

from collections import deque


class CausalAnalyzer:
    """Identify root cause of error cascades using graph analysis."""

    def find_root_cause(self, snapshot: dict, error_events: list[dict]) -> list[dict]:
        """Find root cause candidates using ErrorRank on error subgraph.

        Returns top-3 candidates sorted by confidence score.
        """
        nodes = {n["name"]: n for n in snapshot.get("nodes", [])}
        edges = snapshot.get("edges", [])
        if not edges or not error_events:
            return []

        affected = {e.get("source", "") for e in error_events}
        affected |= {e.get("destination", "") for e in error_events}
        affected = {a for a in affected if a in nodes}

        adj = {}
        reverse_adj = {}
        error_rates = {}
        for edge in edges:
            src, dst = edge["source"], edge["destination"]
            adj.setdefault(src, []).append(dst)
            reverse_adj.setdefault(dst, []).append(src)
            error_rates[src] = max(error_rates.get(src, 0), edge.get("error_rate", 0))

        error_subgraph = {}
        for edge in edges:
            src, dst = edge["source"], edge["destination"]
            if edge.get("error_rate", 0) > 0.01 or src in affected or dst in affected:
                error_subgraph.setdefault(src, []).append(dst)

        upstream = set()
        queue = deque(affected)
        visited = set(affected)
        while queue:
            node = queue.popleft()
            for parent in reverse_adj.get(node, []):
                if parent not in visited:
                    visited.add(parent)
                    upstream.add(parent)
                    queue.append(parent)

        all_candidates = affected | upstream
        if not all_candidates:
            return []

        scores = self._error_pagerank(error_subgraph, error_rates, all_candidates)

        for node in all_candidates:
            distance = self._min_distance(error_subgraph, node, affected)
            if distance > 0:
                scores[node] = scores.get(node, 0) * (1.0 / distance)
            out_degree = len(adj.get(node, []))
            scores[node] = scores.get(node, 0) * (1 + out_degree * 0.1)

        max_score = max(scores.values()) if scores else 1
        if max_score == 0:
            max_score = 1

        results = []
        for node, score in sorted(scores.items(), key=lambda x: -x[1])[:3]:
            downstream = self._find_downstream(adj, node, affected)
            evidence = [e for e in error_events
                        if e.get("source") == node or e.get("destination") == node]
            results.append({
                "service": node,
                "confidence": round(min(score / max_score, 1.0), 2),
                "reason": f"ErrorRank score {score:.3f} with {len(downstream)} affected downstream",
                "affected_downstream": downstream,
                "evidence": evidence[:5],
            })
        return results

    def _error_pagerank(self, adj: dict, error_rates: dict,
                        candidates: set, damping: float = 0.85,
                        iterations: int = 20) -> dict:
        """Modified PageRank weighted by error rates."""
        all_nodes = set(adj.keys())
        for targets in adj.values():
            all_nodes.update(targets)
        all_nodes = all_nodes & candidates if candidates else all_nodes
        if not all_nodes:
            return {}

        n = len(all_nodes)
        scores = {node: 1.0 / n for node in all_nodes}

        for _ in range(iterations):
            new_scores = {}
            for node in all_nodes:
                rank_sum = 0.0
                for src in all_nodes:
                    neighbors = adj.get(src, [])
                    if node in neighbors and len(neighbors) > 0:
                        weight = 1.0 + error_rates.get(src, 0)
                        rank_sum += scores[src] * weight / len(neighbors)
                new_scores[node] = (1 - damping) / n + damping * rank_sum
            scores = new_scores
        return scores

    def _min_distance(self, adj: dict, source: str, targets: set) -> int:
        """BFS shortest distance from source to any target."""
        if source in targets:
            return 1
        visited = {source}
        queue = deque([(source, 0)])
        while queue:
            node, dist = queue.popleft()
            for neighbor in adj.get(node, []):
                if neighbor in targets:
                    return dist + 1
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))
        return 10

    def _find_downstream(self, adj: dict, source: str, affected: set) -> list[str]:
        """Find all affected downstream services via BFS."""
        result = []
        visited = {source}
        queue = deque([source])
        while queue:
            node = queue.popleft()
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    if neighbor in affected:
                        result.append(neighbor)
                    queue.append(neighbor)
        return result
