# integrations/jira_client.py
# Создание Jira тикетов из drift-событий

import requests
from drift.explainer import ExplainCard


class JiraClient:
    """Jira API client для создания тикетов."""

    def __init__(self, url: str, email: str, api_token: str, project_key: str, issue_type: str = "Task"):
        self.url = url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self.project_key = project_key
        self.issue_type = issue_type
        self._open_issues = {}  # edge -> issue_key для дедупликации

    def _headers(self) -> dict:
        """Возвращает headers для API запросов."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _auth(self) -> tuple:
        """Возвращает auth tuple для requests."""
        return (self.email, self.api_token)

    def format_description(self, card: ExplainCard) -> str:
        """Форматирует description в Jira Markdown."""
        desc = f"h2. What Changed\n{card.what_changed}\n\n"
        desc += "h2. Why Risk\n" + "\n".join(f"* {r}" for r in card.why_risk) + "\n\n"
        desc += f"h2. Affected Services\n{', '.join(card.affected)}\n\n"
        desc += f"h2. Recommendation\n{card.recommendation}\n\n"
        desc += "h2. Details\n"
        desc += f"* Risk Score: {card.risk_score}\n"
        desc += f"* Severity: {card.severity}\n"
        desc += f"* Event Type: {card.event_type}\n"

        if card.source and card.destination:
            desc += f"* Connection: {card.source} → {card.destination}\n"

        return desc

    def get_priority(self, severity: str) -> str:
        """Конвертирует severity в Jira priority."""
        priority_map = {
            "critical": "Highest",
            "high": "High",
            "medium": "Medium",
            "low": "Low",
        }
        return priority_map.get(severity, "Medium")

    def create_issue(self, card: ExplainCard) -> dict | None:
        """Создает Jira issue из drift-события.

        Returns:
            dict с полями issue_key, issue_url или None если не создан
        """
        if not self.url or not self.project_key:
            return None

        # Check deduplication
        edge_key = f"{card.source}->{card.destination}" if card.source and card.destination else card.event_type
        if edge_key in self._open_issues:
            return {
                "status": "duplicate",
                "issue_key": self._open_issues[edge_key],
                "issue_url": f"{self.url}/browse/{self._open_issues[edge_key]}",
            }

        try:
            payload = {
                "fields": {
                    "project": {"key": self.project_key},
                    "summary": card.title,
                    "description": self.format_description(card),
                    "issuetype": {"name": self.issue_type},
                    "priority": {"name": self.get_priority(card.severity)},
                    "labels": [
                        "secureguard-drift",
                        f"severity-{card.severity}",
                        f"event-{card.event_type}",
                    ],
                }
            }

            response = requests.post(
                f"{self.url}/rest/api/3/issue",
                json=payload,
                headers=self._headers(),
                auth=self._auth(),
                timeout=30,
            )
            response.raise_for_status()

            result = response.json()
            issue_key = result["key"]

            # Store for deduplication
            self._open_issues[edge_key] = issue_key

            return {
                "status": "created",
                "issue_key": issue_key,
                "issue_url": f"{self.url}/browse/{issue_key}",
            }

        except Exception as e:
            print(f"Failed to create Jira issue: {e}")
            return None

    def mark_issue_closed(self, edge_key: str) -> None:
        """Удаляет issue из списка открытых для дедупликации."""
        self._open_issues.pop(edge_key, None)


if __name__ == "__main__":
    from drift.explainer import ExplainCard

    card = ExplainCard(
        event_type="new_edge",
        title="Test Event",
        what_changed="Test",
        why_risk=["Risk"],
        affected=["svc1"],
        recommendation="Fix",
        risk_score=85,
        severity="critical",
        source="svc1",
        destination="svc2",
        rules_triggered=[],
    )

    client = JiraClient("https://test.atlassian.net", "test@test.com", "token", "TEST")
    print(f"Description:\n{client.format_description(card)}")
