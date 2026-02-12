# api/routes/integration_routes.py
# API endpoints для управления интеграциями

from fastapi import APIRouter, HTTPException
from integrations.config import settings
from integrations.slack_notifier import SlackNotifier
from integrations.jira_client import JiraClient
from integrations.siem_exporter import SIEMExporter
from drift.explainer import ExplainCard

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("/")
async def list_integrations():
    """Возвращает список настроенных интеграций."""
    integrations = []

    if settings.slack_enabled:
        integrations.append({
            "provider": "slack",
            "enabled": True,
            "configured": bool(settings.slack_webhook_url),
            "min_severity": settings.slack_min_severity,
        })

    if settings.jira_enabled:
        integrations.append({
            "provider": "jira",
            "enabled": True,
            "configured": bool(settings.jira_url and settings.jira_project_key),
            "url": settings.jira_url,
            "project_key": settings.jira_project_key,
        })

    if settings.siem_enabled:
        integrations.append({
            "provider": "siem",
            "enabled": True,
            "configured": True,
            "transport": settings.siem_transport,
        })

    return {"integrations": integrations, "count": len(integrations)}


@router.post("/slack/test")
async def test_slack():
    """Тестирует Slack webhook."""
    if not settings.slack_webhook_url:
        raise HTTPException(status_code=400, detail="Slack webhook URL not configured")

    # Create test card
    test_card = ExplainCard(
        event_type="test",
        title="🧪 Test Notification from SecureGuard Drift",
        what_changed="This is a test notification to verify Slack integration",
        why_risk=["This is a test message"],
        affected=["test-service"],
        recommendation="If you see this, the integration is working!",
        risk_score=0,
        severity="low",
        source="test-source",
        destination="test-dest",
        rules_triggered=["test"],
    )

    notifier = SlackNotifier(settings.slack_webhook_url, min_severity="low")

    try:
        success = notifier.send_notification(test_card)
        if success:
            return {"status": "success", "message": "Test notification sent to Slack"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send test notification")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/jira/test")
async def test_jira():
    """Тестирует Jira подключение."""
    if not settings.jira_url or not settings.jira_project_key:
        raise HTTPException(status_code=400, detail="Jira not configured")

    # Test with simple API call
    import requests

    try:
        response = requests.get(
            f"{settings.jira_url}/rest/api/3/myself",
            auth=(settings.jira_email, settings.jira_api_token),
            timeout=10,
        )
        response.raise_for_status()

        user_info = response.json()
        return {
            "status": "success",
            "message": "Connected to Jira successfully",
            "user": user_info.get("displayName", user_info.get("emailAddress")),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to Jira: {str(e)}")


@router.post("/siem/test")
async def test_siem():
    """Тестирует SIEM экспорт."""
    if not settings.siem_enabled:
        raise HTTPException(status_code=400, detail="SIEM not enabled")

    # Create test card
    test_card = ExplainCard(
        event_type="test",
        title="Test SIEM Event",
        what_changed="Test",
        why_risk=["Test"],
        affected=["test"],
        recommendation="Test",
        risk_score=0,
        severity="low",
        source="test",
        destination="test",
        rules_triggered=[],
    )

    exporter = SIEMExporter(
        transport=settings.siem_transport,
        syslog_host=settings.siem_syslog_host,
        syslog_port=settings.siem_syslog_port,
        syslog_protocol=settings.siem_syslog_protocol,
        webhook_url=settings.siem_webhook_url,
    )

    try:
        cef_message = exporter.format_cef(test_card)
        return {
            "status": "success",
            "message": "SIEM export test (CEF format generated)",
            "cef_sample": cef_message[:100] + "...",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
