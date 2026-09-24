from fastapi import APIRouter

from app.config import get_settings
from app.data.loader import load_tickets
from app.models.schemas import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        rows_loaded=len(load_tickets()),
        llm_provider=settings.llm_provider,
    )
