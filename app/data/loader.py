import csv
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings


REQUIRED_COLUMNS = {
    "ticket_id",
    "created_at",
    "category",
    "priority",
    "status",
    "response_time_hrs",
    "resolution_time_hrs",
    "agent_id",
    "customer_rating",
    "issue_summary",
}

ALLOWED_CATEGORIES = {"Billing", "Technical", "General"}
ALLOWED_PRIORITIES = {"Low", "Medium", "High", "Critical"}
ALLOWED_STATUSES = {"Open", "Resolved", "Escalated"}


def _float_or_none(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    return float(value)


def _int_or_none(value: str | None) -> int | None:
    if value is None or value.strip() == "":
        return None
    return int(float(value))


@lru_cache
def load_tickets(data_path: str | None = None) -> tuple[dict[str, Any], ...]:
    """Load and normalize the CSV once per process."""

    path = Path(data_path or get_settings().data_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise FileNotFoundError(f"Ticket dataset not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")

        records = []
        seen_ids: set[str] = set()
        for line_number, row in enumerate(reader, start=2):
            ticket_id = row["ticket_id"].strip()
            category = row["category"].strip()
            priority = row["priority"].strip()
            status = row["status"].strip()
            if not ticket_id or ticket_id in seen_ids:
                raise ValueError(f"Invalid or duplicate ticket_id on CSV line {line_number}")
            if category not in ALLOWED_CATEGORIES:
                raise ValueError(f"Invalid category on CSV line {line_number}: {category}")
            if priority not in ALLOWED_PRIORITIES:
                raise ValueError(f"Invalid priority on CSV line {line_number}: {priority}")
            if status not in ALLOWED_STATUSES:
                raise ValueError(f"Invalid status on CSV line {line_number}: {status}")
            try:
                created_at = datetime.strptime(row["created_at"].strip(), "%Y-%m-%d %H:%M")
                response_time = _float_or_none(row["response_time_hrs"])
                resolution_time = _float_or_none(row["resolution_time_hrs"])
                customer_rating = _int_or_none(row["customer_rating"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid typed value on CSV line {line_number}") from exc
            if response_time is not None and response_time < 0:
                raise ValueError(f"Negative response time on CSV line {line_number}")
            if resolution_time is not None and resolution_time < 0:
                raise ValueError(f"Negative resolution time on CSV line {line_number}")
            if customer_rating is not None and not 1 <= customer_rating <= 5:
                raise ValueError(f"Customer rating must be 1-5 on CSV line {line_number}")
            seen_ids.add(ticket_id)
            records.append(
                {
                    "ticket_id": ticket_id,
                    "created_at": created_at,
                    "category": category,
                    "priority": priority,
                    "status": status,
                    "response_time_hrs": response_time,
                    "resolution_time_hrs": resolution_time,
                    "agent_id": row["agent_id"].strip(),
                    "customer_rating": customer_rating,
                    "issue_summary": row["issue_summary"].strip(),
                }
            )
    return tuple(records)
