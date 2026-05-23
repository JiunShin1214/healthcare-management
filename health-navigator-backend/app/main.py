from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from app.routers.health_check import router as health_check_router
from app.routers.auth import router as auth_router
from app.routers.symptom_checker import gemini_router, router as symptom_checker_router
from app.routers import drugs
from app.models import user
from app.models import user_medication
from app.models import drug
from app.models import health_check

from app.core.database import Base, engine
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Health Navigator Backend",
    version="1.0.0"
)

app.include_router(health_check_router, prefix="/health-check", tags=["health-check"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(symptom_checker_router)
app.include_router(gemini_router)
app.include_router(drugs.router)


DEMO_DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
SYMPTOM_FLOW_DEMO_HTML = DEMO_DOCS_DIR / "symptom_checker_flow_demo.html"


@app.get("/")
def root():
    return {"message": "Health Navigator Backend is running"}


@app.get("/demo/symptom-checker-flow", include_in_schema=False)
def symptom_checker_flow_demo():
    if not SYMPTOM_FLOW_DEMO_HTML.exists():
        raise HTTPException(status_code=404, detail="Symptom checker flow demo HTML not found.")
    return FileResponse(SYMPTOM_FLOW_DEMO_HTML)
