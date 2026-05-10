from fastapi import FastAPI
from app.routers.health_check import router as health_check_router
from app.routers.auth import router as auth_router
from app.routers.symptom_checker import router as symptom_checker_router
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
app.include_router(drugs.router)


@app.get("/")
def root():
    return {"message": "Health Navigator Backend is running"}

