# collector/otel_receiver.py
# Приём OTEL-трасс (gRPC или HTTP)

import json
import logging
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SpanData:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    service_name: str
    operation_name: str
    start_time: datetime
    end_time: datetime
    status_code: int = 0
    attributes: Dict = field(default_factory=dict)


@dataclass
class TraceData:
    trace_id: str
    spans: List[SpanData] = field(default_factory=list)


class OTELReceiver:
    """Приёмник OpenTelemetry трасс через HTTP (OTLP/HTTP)."""

    def __init__(self, host: str = "0.0.0.0", port: int = 4318, on_trace: Optional[Callable] = None):
        self.host = host
        self.port = port
        self.on_trace = on_trace
        self._traces: List[TraceData] = []

    def parse_otlp_json(self, payload: Dict) -> List[TraceData]:
        """Парсинг OTLP JSON payload в список трасс."""
        traces = []
        resource_spans = payload.get("resourceSpans", [])

        for rs in resource_spans:
            resource = rs.get("resource", {})
            service_name = "unknown"
            for attr in resource.get("attributes", []):
                if attr.get("key") == "service.name":
                    service_name = attr.get("value", {}).get("stringValue", "unknown")
                    break

            scope_spans = rs.get("scopeSpans", [])
            for ss in scope_spans:
                for span in ss.get("spans", []):
                    trace_id = span.get("traceId", "")
                    span_data = SpanData(
                        trace_id=trace_id,
                        span_id=span.get("spanId", ""),
                        parent_span_id=span.get("parentSpanId") or None,
                        service_name=service_name,
                        operation_name=span.get("name", ""),
                        start_time=self._nano_to_datetime(span.get("startTimeUnixNano", 0)),
                        end_time=self._nano_to_datetime(span.get("endTimeUnixNano", 0)),
                        status_code=span.get("status", {}).get("code", 0),
                        attributes=self._parse_attributes(span.get("attributes", [])),
                    )

                    existing = next((t for t in traces if t.trace_id == trace_id), None)
                    if existing:
                        existing.spans.append(span_data)
                    else:
                        traces.append(TraceData(trace_id=trace_id, spans=[span_data]))

        return traces

    def extract_edges(self, traces: List[TraceData]) -> List[Dict]:
        """Извлечение рёбер графа из трасс (parent_service → child_service)."""
        edges = []
        for trace in traces:
            span_map = {s.span_id: s for s in trace.spans}
            for span in trace.spans:
                if span.parent_span_id and span.parent_span_id in span_map:
                    parent = span_map[span.parent_span_id]
                    if parent.service_name != span.service_name:
                        duration_ms = (span.end_time - span.start_time).total_seconds() * 1000
                        edges.append({
                            "source": parent.service_name,
                            "target": span.service_name,
                            "operation": span.operation_name,
                            "duration_ms": duration_ms,
                            "status_code": span.status_code,
                            "trace_id": trace.trace_id,
                            "timestamp": span.start_time.isoformat(),
                        })
        return edges

    async def start_http_server(self):
        """Запуск HTTP-сервера для приёма OTLP/HTTP трасс."""
        from aiohttp import web

        async def handle_traces(request: web.Request) -> web.Response:
            try:
                payload = await request.json()
                traces = self.parse_otlp_json(payload)
                self._traces.extend(traces)
                if self.on_trace:
                    for trace in traces:
                        self.on_trace(trace)
                logger.info(f"Received {len(traces)} traces")
                return web.json_response({"status": "ok"})
            except Exception as e:
                logger.error(f"Error processing traces: {e}")
                return web.json_response({"error": str(e)}, status=400)

        app = web.Application()
        app.router.add_post("/v1/traces", handle_traces)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        logger.info(f"OTEL HTTP receiver listening on {self.host}:{self.port}")
        await site.start()

    def get_collected_traces(self) -> List[TraceData]:
        return list(self._traces)

    @staticmethod
    def _nano_to_datetime(nano: int) -> datetime:
        return datetime.fromtimestamp(nano / 1e9) if nano else datetime.min

    @staticmethod
    def _parse_attributes(attrs: List[Dict]) -> Dict:
        result = {}
        for attr in attrs:
            key = attr.get("key", "")
            value = attr.get("value", {})
            if "stringValue" in value:
                result[key] = value["stringValue"]
            elif "intValue" in value:
                result[key] = int(value["intValue"])
            elif "doubleValue" in value:
                result[key] = float(value["doubleValue"])
            elif "boolValue" in value:
                result[key] = bool(value["boolValue"])
        return result
