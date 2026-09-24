from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class Ticket(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ticket_id: str
    created_at: datetime
    category: str
    priority: str
    status: str
    response_time_hrs: float | None = None
    resolution_time_hrs: float | None = None
    agent_id: str
    customer_rating: int | None = None
    issue_summary: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    intent: str
    model: str
    data: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[Ticket] = Field(default_factory=list)


class AnomalyRequest(BaseModel):
    hours_threshold: float = Field(default=24.0, gt=0, le=720)
    limit: int = Field(default=50, ge=1, le=200)


class Anomaly(BaseModel):
    anomaly_type: Literal["long_resolution", "stale_unresolved", "response_time_spike"]
    severity: Literal["medium", "high", "critical"]
    reason: str
    ticket: Ticket


class AnomalyResponse(BaseModel):
    reference_time: datetime
    thresholds: dict[str, float]
    summary: dict[str, int]
    anomalies: list[Anomaly]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    rows_loaded: int
    llm_provider: str
