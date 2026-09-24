from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.anomaly import router as anomaly_router
from app.api.health import router as health_router
from app.api.query import router as query_router
from app.config import get_settings


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    description="Grounded natural-language analytics and anomaly detection for support tickets.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(query_router)
app.include_router(anomaly_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": settings.app_name, "docs": "/docs", "health": "/health"}
