from fastapi import APIRouter
from app.routers.api.projects import router as projects_router
from app.routers.api.budget import router as budget_router
from app.routers.api.expenses import router as expenses_router
from app.routers.api.transfers import router as transfers_router
from app.routers.api.logical_framework import router as logical_framework_router
from app.routers.api.documents import router as documents_router
from app.routers.api.verification_sources import router as verification_sources_router
from app.routers.api.reports import router as reports_router
from app.routers.api.users import router as users_router
from app.routers.api.audit import router as audit_router

api_router = APIRouter(prefix="/api")
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(budget_router, tags=["budget"])
api_router.include_router(expenses_router, tags=["expenses"])
api_router.include_router(transfers_router, tags=["transfers"])
api_router.include_router(logical_framework_router, tags=["logical-framework"])
api_router.include_router(documents_router, tags=["documents"])
api_router.include_router(verification_sources_router, tags=["verification-sources"])
api_router.include_router(reports_router, tags=["reports"])
api_router.include_router(users_router, tags=["users"])
api_router.include_router(audit_router, tags=["audit"])
