from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.data.loader import load_tickets
from app.models.schemas import QueryRequest, QueryResponse, Ticket
from app.services.query_service import QueryService


router = APIRouter(prefix="/api", tags=["query"])


@router.get("/tickets", response_model=list[Ticket])
def list_tickets(
    limit: int = Query(default=100, ge=1, le=500),
    status: Literal["Open", "Resolved", "Escalated"] | None = None,
) -> list[Ticket]:
    rows = load_tickets()
    if status:
        rows = tuple(row for row in rows if row["status"] == status)
    return [Ticket.model_validate(row) for row in rows[:limit]]


@router.post("/query", response_model=QueryResponse)
def query_tickets(request: QueryRequest) -> QueryResponse:
    try:
        result = QueryService(get_settings()).run(request.question, load_tickets())
        return QueryResponse.model_validate(result)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
