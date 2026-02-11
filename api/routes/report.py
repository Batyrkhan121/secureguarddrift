# api/routes/report.py
# GET/POST экспорт отчёта

import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from typing import Optional

from graph.storage import SQLiteStorage
from drift.detector import DriftDetector
from drift.scorer import RiskScorer
from drift.explainer import DriftExplainer

router = APIRouter()
storage = SQLiteStorage()
detector = DriftDetector()
scorer = RiskScorer()
explainer = DriftExplainer()


@router.get("/generate")
async def generate_report(
    before: Optional[str] = Query(None, description="ID снапшота 'до'"),
    after: Optional[str] = Query(None, description="ID снапшота 'после'"),
    format: str = Query(default="json", description="Формат: json или markdown"),
):
    """Сгенерировать отчёт о дрифте."""
    # Определяем снапшоты
    if after:
        snap_after = storage.load(after)
    else:
        snap_after = storage.get_latest()

    if not snap_after:
        raise HTTPException(status_code=404, detail="No snapshots available")

    if before:
        snap_before = storage.load(before)
    else:
        snap_before = storage.get_previous(snap_after.id)

    if not snap_before:
        raise HTTPException(status_code=404, detail="Need at least two snapshots for a report")

    # Анализ
    events = detector.compare(snap_before, snap_after)
    risk = scorer.score_events(events)
    explanations = explainer.explain_all(events)
    summary = explainer.generate_summary(events)

    report = {
        "title": "SecureGuardDrift Report",
        "generated_at": datetime.utcnow().isoformat(),
        "snapshot_before": {
            "id": snap_before.id,
            "timestamp": snap_before.timestamp,
            "nodes": len(snap_before.nodes),
            "edges": len(snap_before.edges),
        },
        "snapshot_after": {
            "id": snap_after.id,
            "timestamp": snap_after.timestamp,
            "nodes": len(snap_after.nodes),
            "edges": len(snap_after.edges),
        },
        "risk_assessment": risk,
        "explanations": explanations,
        "summary": summary,
    }

    if format == "markdown":
        md = _report_to_markdown(report)
        return PlainTextResponse(content=md, media_type="text/markdown")

    return report


@router.post("/export")
async def export_report(report_data: dict):
    """Экспортировать пользовательский отчёт."""
    report_data["exported_at"] = datetime.utcnow().isoformat()
    return {"status": "ok", "report": report_data}


def _report_to_markdown(report: dict) -> str:
    """Конвертация отчёта в Markdown."""
    lines = [
        f"# {report['title']}",
        f"**Дата:** {report['generated_at']}",
        "",
        "## Снапшоты",
        f"- **До:** {report['snapshot_before']['id']} ({report['snapshot_before']['timestamp']})",
        f"  - Узлов: {report['snapshot_before']['nodes']}, Рёбер: {report['snapshot_before']['edges']}",
        f"- **После:** {report['snapshot_after']['id']} ({report['snapshot_after']['timestamp']})",
        f"  - Узлов: {report['snapshot_after']['nodes']}, Рёбер: {report['snapshot_after']['edges']}",
        "",
        "## Оценка рисков",
        f"- **Общий score:** {report['risk_assessment'].get('total_score', 0)}",
        f"- **Уровень риска:** {report['risk_assessment'].get('risk_level', 'unknown')}",
        f"- **Событий:** {report['risk_assessment'].get('event_count', 0)}",
        f"- **Критических:** {report['risk_assessment'].get('critical_count', 0)}",
        "",
        "## Резюме",
        report.get("summary", ""),
        "",
        "## Детали событий",
    ]

    for exp in report.get("explanations", []):
        lines.append(f"\n### {exp.get('title', '')}")
        lines.append(f"**Severity:** {exp.get('severity', '')}")
        lines.append(exp.get("detail", ""))
        lines.append(f"**Рекомендация:** {exp.get('action', '')}")

    return "\n".join(lines)
