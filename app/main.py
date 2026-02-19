import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from app.config import get_settings
from app.database import engine, Base, SessionLocal
from app.auth.middleware import AuthMiddleware
from app.routers.api import api_router
from app.views.projects import router as projects_router
from app.views.budget import router as budget_router
from app.views.expenses import router as expenses_router
from app.views.transfers import router as transfers_router
from app.views.logical_framework import router as logical_framework_router
from app.views.documents import router as documents_router
from app.views.verification_sources import router as verification_sources_router
from app.views.reports import router as reports_router
from app.views.auth import router as auth_router
from app.views.users import router as users_router
from app.views.counterpart import router as counterpart_router
from app.views.audit import router as audit_router
from app.views.postponements import router as postponements_router
from app.services.project_service import ProjectService
from app.services.budget_service import BudgetService

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables and seed data
    Base.metadata.create_all(bind=engine)

    # Migration: add language column to counterpart_sessions if missing
    from sqlalchemy import inspect as sa_inspect, text
    inspector = sa_inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("counterpart_sessions")]
    if "language" not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE counterpart_sessions ADD COLUMN language VARCHAR(5) DEFAULT 'es'"))
            conn.commit()

    # Migration: add funding_source_id column to expenses if missing
    expense_columns = [c["name"] for c in inspector.get_columns("expenses")]
    if "funding_source_id" not in expense_columns:
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE expenses ADD COLUMN funding_source_id INTEGER "
                "REFERENCES project_funding_sources(id) ON DELETE SET NULL"
            ))
            conn.commit()

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

        # Migration: create default funding sources for existing projects with budgets
        from app.models.project import Project as ProjectModel
        from app.models.funding import FuenteFinanciacion
        from sqlalchemy import select as sa_select, func as sa_func
        projects_with_budget = db.execute(
            sa_select(ProjectModel)
            .where(ProjectModel.funder_id.isnot(None))
        ).scalars().all()
        for proj in projects_with_budget:
            existing_sources = db.execute(
                sa_select(sa_func.count(FuenteFinanciacion.id))
                .where(FuenteFinanciacion.project_id == proj.id)
            ).scalar()
            if existing_sources == 0:
                budget_service.auto_create_default_sources(proj)
                # Try to map existing expense financiado_por to funding sources
                from app.models.expense import Expense as ExpenseModel
                sources = budget_service.get_project_funding_sources(proj.id)
                source_map = {s.nombre.lower(): s.id for s in sources}
                expenses = db.execute(
                    sa_select(ExpenseModel)
                    .where(
                        ExpenseModel.project_id == proj.id,
                        ExpenseModel.funding_source_id.is_(None),
                    )
                ).scalars().all()
                for exp in expenses:
                    if exp.financiado_por:
                        matched_id = source_map.get(exp.financiado_por.lower())
                        if matched_id:
                            exp.funding_source_id = matched_id
                db.commit()
    finally:
        db.close()

    yield
    # Shutdown: nothing to do


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

# Middleware (order matters: last added = first executed)
app.add_middleware(AuthMiddleware)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers - auth first (no prefix)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(counterpart_router)
app.include_router(audit_router)

# API
app.include_router(api_router)

# Views
app.include_router(projects_router, prefix="/projects")
app.include_router(budget_router, prefix="/projects")
app.include_router(expenses_router, prefix="/projects")
app.include_router(transfers_router, prefix="/projects")
app.include_router(logical_framework_router, prefix="/projects")
app.include_router(documents_router, prefix="/projects")
app.include_router(verification_sources_router, prefix="/projects")
app.include_router(reports_router, prefix="/projects")
app.include_router(postponements_router, prefix="/projects")


@app.get("/")
def root():
    return RedirectResponse(url="/projects")


@app.get("/health")
def health():
    return {"status": "ok"}
