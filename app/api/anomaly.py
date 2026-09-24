from fastapi import APIRouter, HTTPException

from app.data.loader import load_tickets
from app.models.schemas import AnomalyRequest, AnomalyResponse
from app.services.anomaly_service import AnomalyService


router = APIRouter(prefix="/api", tags=["anomaly"])


@router.post("/anomalies", response_model=AnomalyResponse)
def detect_anomalies(request: AnomalyRequest) -> AnomalyResponse:
    try:
        result = AnomalyService().detect(load_tickets(), request.hours_threshold, request.limit)
        return AnomalyResponse.model_validate(result)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
