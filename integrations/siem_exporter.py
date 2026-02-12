# integrations/siem_exporter.py
# Экспорт drift-событий в SIEM в формате CEF

import socket
import requests
from datetime import datetime, timezone
from drift.explainer import ExplainCard


class SIEMExporter:
    """Экспорт drift-событий в SIEM (CEF format)."""

    def __init__(
        self,
        transport: str = "syslog",
        syslog_host: str = "localhost",
        syslog_port: int = 514,
        syslog_protocol: str = "udp",
        webhook_url: str = "",
    ):
        self.transport = transport
        self.syslog_host = syslog_host
        self.syslog_port = syslog_port
        self.syslog_protocol = syslog_protocol
        self.webhook_url = webhook_url

    def format_cef(self, card: ExplainCard) -> str:
        """Форматирует событие в CEF (Common Event Format).

        CEF:0|Vendor|Product|Version|SignatureID|Name|Severity|Extension
        """
        # CEF version
        version = "CEF:0"

        # Vendor and product info
        vendor = "SecureGuardDrift"
        product = "ServiceMesh Security"
        product_version = "0.1.0"

        # Signature ID (event type)
        signature_id = card.event_type

        # Name (title)
        name = card.title.replace("|", "_")

        # Severity (0-10 scale for CEF)
        severity_map = {
            "critical": "10",
            "high": "7",
            "medium": "5",
            "low": "3",
        }
        severity = severity_map.get(card.severity, "5")

        # Extensions (key-value pairs)
        extensions = []
        extensions.append(f"src={card.source or 'unknown'}")
        extensions.append(f"dst={card.destination or 'unknown'}")
        extensions.append(f"cs1={card.risk_score}")
        extensions.append("cs1Label=RiskScore")
        extensions.append(f"cs2={card.severity}")
        extensions.append("cs2Label=Severity")
        extensions.append(f"cs3={','.join(card.affected)}")
        extensions.append("cs3Label=AffectedServices")
        extensions.append(f"msg={card.what_changed.replace('|', '_')}")

        extension = " ".join(extensions)

        # Combine
        cef_message = f"{version}|{vendor}|{product}|{product_version}|{signature_id}|{name}|{severity}|{extension}"

        return cef_message

    def send_syslog(self, message: str) -> bool:
        """Отправляет сообщение через syslog."""
        try:
            # Syslog header: <Priority>Timestamp Hostname Tag: Message
            priority = 134  # Local0.Info
            timestamp = datetime.now(timezone.utc).strftime("%b %d %H:%M:%S")
            hostname = socket.gethostname()
            tag = "SecureGuardDrift"

            syslog_message = f"<{priority}>{timestamp} {hostname} {tag}: {message}\n"

            if self.syslog_protocol == "udp":
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(syslog_message.encode(), (self.syslog_host, self.syslog_port))
                sock.close()
            else:  # tcp
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((self.syslog_host, self.syslog_port))
                sock.send(syslog_message.encode())
                sock.close()

            return True

        except Exception as e:
            print(f"Failed to send syslog: {e}")
            return False

    def send_webhook(self, message: str, card: ExplainCard) -> bool:
        """Отправляет событие через HTTP webhook."""
        try:
            payload = {
                "cef_message": message,
                "event_type": card.event_type,
                "severity": card.severity,
                "risk_score": card.risk_score,
                "source": card.source,
                "destination": card.destination,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            return True

        except Exception as e:
            print(f"Failed to send webhook: {e}")
            return False

    def export_event(self, card: ExplainCard) -> bool:
        """Экспортирует событие в SIEM."""
        cef_message = self.format_cef(card)

        if self.transport == "syslog":
            return self.send_syslog(cef_message)
        elif self.transport == "webhook":
            return self.send_webhook(cef_message, card)
        return False


if __name__ == "__main__":
    card = ExplainCard(
        event_type="new_edge",
        title="Test Event",
        what_changed="Test",
        why_risk=["Risk"],
        affected=["svc1", "svc2"],
        recommendation="Fix",
        risk_score=85,
        severity="critical",
        source="svc1",
        destination="svc2",
        rules_triggered=[],
    )

    exporter = SIEMExporter()
    print(f"CEF: {exporter.format_cef(card)}")
