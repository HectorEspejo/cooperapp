import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.config import get_settings
from app.database import engine, Base, SessionLocal
from app.routers.api import api_router
from app.views.projects import router as projects_router
from app.views.budget import router as budget_router
from app.views.expenses import router as expenses_router
from app.views.transfers import router as transfers_router
from app.views.logical_framework import router as logical_framework_router
from app.views.documents import router as documents_router
from app.views.verification_sources import router as verification_sources_router
from app.views.reports import router as reports_router
from app.services.project_service import ProjectService
from app.services.budget_service import BudgetService

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables and seed data
    Base.metadata.create_all(bind=engine)

    # Create uploads directory for expense documents
    os.makedirs("uploads", exist_ok=True)

    # Create exports directory for generated reports
    os.makedirs("exports", exist_ok=True)

    # Seed data
    db = SessionLocal()
    try:
        project_service = ProjectService(db)
        project_service.seed_ods()

        budget_service = BudgetService(db)
        budget_service.seed_funders()
        budget_service.seed_aacid_templates()
        budget_service.seed_aecid_templates()
        budget_service.seed_dipu_templates()
        budget_service.seed_ayto_templates()
    finally:
        db.close()

    yield
    # Shutdown: nothing to do


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers
app.include_router(api_router)
app.include_router(projects_router, prefix="/projects")
app.include_router(budget_router, prefix="/projects")
app.include_router(expenses_router, prefix="/projects")
app.include_router(transfers_router, prefix="/projects")
app.include_router(logical_framework_router, prefix="/projects")
app.include_router(documents_router, prefix="/projects")
app.include_router(verification_sources_router, prefix="/projects")
app.include_router(reports_router, prefix="/projects")


@app.get("/")
def root():
    return RedirectResponse(url="/projects")


@app.get("/health")
def health():
    return {"status": "ok"}
