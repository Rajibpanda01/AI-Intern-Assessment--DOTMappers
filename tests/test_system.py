from pathlib import Path

import pytest

from app.config import Settings
from app.data.loader import load_tickets
from app.services.anomaly_service import AnomalyService
from app.services.llm_service import LLMService, QueryPlan
from app.services.query_service import QueryService


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = str(ROOT / "data" / "support_tickets.csv")


def settings() -> Settings:
    return Settings(data_path=DATA_PATH, llm_provider="none")


def test_loader_reads_and_normalizes_supplied_dataset() -> None:
    rows = load_tickets(DATA_PATH)

    assert len(rows) == 500
    assert rows[0]["ticket_id"] == "TKT-001"
    assert rows[0]["created_at"].isoformat(timespec="minutes") == "2024-02-05T11:14"
    assert rows[0]["response_time_hrs"] == 3.7


def test_sample_natural_language_queries_are_grounded() -> None:
    service = QueryService(settings())
    rows = load_tickets(DATA_PATH)

    open_result = service.run("How many tickets are currently open?", rows)
    critical_result = service.run("Show me all Critical tickets not resolved within 12 hours.", rows)
    rating_result = service.run("What is the average customer rating for Technical category tickets?", rows)

    assert open_result["data"] == [{"count": 111}]
    assert len(critical_result["evidence"]) == 8
    assert len(critical_result["data"]) == 8
    assert all(ticket["priority"] == "Critical" for ticket in critical_result["data"])
    assert rating_result["data"] == [{"average_rating": 3.74, "rated_tickets": 104}]


def test_anomaly_response_has_bounded_summary() -> None:
    result = AnomalyService().detect(load_tickets(DATA_PATH), hours_threshold=24, limit=20)

    assert result["summary"]["total"] == len(result["anomalies"]) == 20
    assert set(result["summary"]) == {"total", "critical", "high", "medium"}
    assert all(item["ticket"]["ticket_id"].startswith("TKT-") for item in result["anomalies"])


def test_llm_plan_validation_rejects_untrusted_intent() -> None:
    plan = LLMService._validated_plan(
        {
            "intent": "count",
            "priority": "Critical",
            "category": None,
            "status": "unresolved",
            "time_window": None,
            "unresolved_within_hrs": 12,
        }
    )

    assert plan == QueryPlan(
        intent="count",
        priority="Critical",
        status="unresolved",
        unresolved_within_hrs=12.0,
    )

    with pytest.raises(ValueError):
        LLMService._validated_plan({"intent": "drop_database"})
