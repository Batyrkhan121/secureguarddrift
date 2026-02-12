"""Blast radius prediction for service failures."""

from collections import deque


class BlastRadiusPredictor:
    """Predict which services will be affected if a service fails."""

    def predict(self, snapshot: dict, failing_service: str,
                failure_mode: str = "error") -> dict:
        """Predict blast radius using BFS with probability decay.

        Returns affected services with probability, time to impact, and severity.
        """
        nodes = {n["name"]: n for n in snapshot.get("nodes", [])}
        edges = snapshot.get("edges", [])

        if failing_service not in nodes:
            return {
                "failing_service": failing_service,
                "failure_mode": failure_mode,
                "affected": [],
                "total_blast_radius": 0,
                "estimated_recovery_minutes": 0,
            }

        adj: dict[str, list[dict]] = {}
        for edge in edges:
            src = edge["source"]
            adj.setdefault(src, []).append(edge)

        affected = []
        visited = {failing_service}
        queue = deque([(failing_service, 1.0, 0)])

        while queue:
            node, prob, depth = queue.popleft()
            for edge in adj.get(node, []):
                dst = edge["destination"]
                if dst in visited:
                    continue
                visited.add(dst)

                error_rate = edge.get("error_rate", 0.1)
                request_count = edge.get("request_count", 1)
                decay = 0.8 if failure_mode == "error" else 0.6

                edge_prob = prob * decay * (1 + error_rate)
                edge_prob = min(edge_prob, 1.0)

                req_per_min = max(request_count / 60, 0.1)
                time_to_impact = round(max(1, (depth + 1) * (5 / req_per_min)), 1)

                node_type = nodes.get(dst, {}).get("node_type", "service")
                if node_type == "database":
                    impact = "critical"
                elif edge_prob > 0.7:
                    impact = "high"
                elif edge_prob > 0.4:
                    impact = "medium"
                else:
                    impact = "low"

                affected.append({
                    "service": dst,
                    "probability": round(edge_prob, 2),
                    "time_to_impact_minutes": time_to_impact,
                    "impact": impact,
                })

                if edge_prob > 0.1 and depth < 10:
                    queue.append((dst, edge_prob, depth + 1))

        affected.sort(key=lambda x: -x["probability"])

        recovery = max((a["time_to_impact_minutes"] for a in affected), default=0)
        recovery = round(recovery * 1.5 + 5, 1) if affected else 0

        return {
            "failing_service": failing_service,
            "failure_mode": failure_mode,
            "affected": affected,
            "total_blast_radius": len(affected),
            "estimated_recovery_minutes": recovery,
        }
