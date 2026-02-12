# integrations/config.py
# Конфигурация для всех интеграций (Slack, Jira, SIEM)

from pydantic_settings import BaseSettings, SettingsConfigDict


class IntegrationsSettings(BaseSettings):
    """Настройки для всех интеграций."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Slack settings
    slack_enabled: bool = False
    slack_webhook_url: str = ""
    slack_min_severity: str = "high"  # "critical", "high", "medium", "low"
    slack_rate_limit_seconds: int = 60

    # Jira settings
    jira_enabled: bool = False
    jira_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""
    jira_issue_type: str = "Task"

    # SIEM settings
    siem_enabled: bool = False
    siem_transport: str = "syslog"  # "syslog" or "webhook"
    siem_syslog_host: str = "localhost"
    siem_syslog_port: int = 514
    siem_syslog_protocol: str = "udp"  # "udp" or "tcp"
    siem_webhook_url: str = ""

    # Notification router rules
    router_critical_targets: str = "slack,jira"  # comma-separated
    router_high_targets: str = "slack"
    router_medium_targets: str = "siem"
    router_low_targets: str = ""


# Global settings instance
settings = IntegrationsSettings()


if __name__ == "__main__":
    print("Integrations Settings:")
    print(f"  Slack enabled: {settings.slack_enabled}")
    print(f"  Jira enabled: {settings.jira_enabled}")
    print(f"  SIEM enabled: {settings.siem_enabled}")
