"""Pre-deployment drift prediction from planned changes."""


class DriftPredictor:
    """Predict drift BEFORE deployment based on planned changes."""

    def predict_from_diff(self, current_snapshot: dict,
                          planned_changes: dict) -> list[dict]:
        """Predict drift events from planned service/edge changes.

        Args:
            current_snapshot: Current service graph snapshot.
            planned_changes: Dict with keys:
                add_services, remove_services, add_edges, modify_configs
        """
        predictions = []
        existing_nodes = {n["name"] for n in current_snapshot.get("nodes", [])}
        existing_edges = {
            (e["source"], e["destination"])
            for e in current_snapshot.get("edges", [])
        }

        for svc in planned_changes.get("add_services", []):
            name = svc if isinstance(svc, str) else svc.get("name", "")
            predictions.append({
                "predicted_event": "new_service",
                "source": name,
                "destination": "",
                "predicted_severity": "medium",
                "recommendation": f"Monitor {name} after deployment for unexpected connections",
            })

        for svc in planned_changes.get("remove_services", []):
            name = svc if isinstance(svc, str) else svc.get("name", "")
            if name in existing_nodes:
                broken = [(s, d) for s, d in existing_edges if s == name or d == name]
                severity = "critical" if len(broken) > 3 else "high"
                predictions.append({
                    "predicted_event": "removed_service",
                    "source": name,
                    "destination": "",
                    "predicted_severity": severity,
                    "recommendation": f"Removing {name} will break {len(broken)} connections. "
                                      f"Ensure all dependents are updated.",
                })

        for edge in planned_changes.get("add_edges", []):
            src = edge.get("source", "")
            dst = edge.get("destination", "")
            if (src, dst) not in existing_edges:
                severity = "low" if src in existing_nodes and dst in existing_nodes else "medium"
                predictions.append({
                    "predicted_event": "new_edge",
                    "source": src,
                    "destination": dst,
                    "predicted_severity": severity,
                    "recommendation": f"New connection {src} → {dst}. Verify error handling and timeouts.",
                })

        for cfg in planned_changes.get("modify_configs", []):
            service = cfg.get("service", "")
            change_type = cfg.get("type", "config_change")
            severity = "high" if change_type in ("replicas", "resources", "env") else "low"
            predictions.append({
                "predicted_event": "config_change",
                "source": service,
                "destination": "",
                "predicted_severity": severity,
                "recommendation": f"Config change on {service} ({change_type}). "
                                  f"Monitor latency and error rates post-deploy.",
            })

        return predictions
