from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import Permiso
from app.services.budget_service import BudgetService
from app.schemas.budget import (
    FunderResponse,
    BudgetLineTemplateResponse,
    ProjectBudgetLineResponse,
    ProjectBudgetLineUpdate,
    BudgetSummary,
)

router = APIRouter()


def get_service(db: Session = Depends(get_db)) -> BudgetService:
    return BudgetService(db)


@router.get("/funders", response_model=list[FunderResponse])
def list_funders(
    user: User = Depends(require_permission(Permiso.presupuesto_ver)),
    service: BudgetService = Depends(get_service),
):
    """List all available funders"""
    return service.get_all_funders()


@router.get("/funders/{funder_id}", response_model=FunderResponse)
def get_funder(
    funder_id: int,
    user: User = Depends(require_permission(Permiso.presupuesto_ver)),
    service: BudgetService = Depends(get_service),
):
    """Get a specific funder by ID"""
    funder = service.get_funder_by_id(funder_id)
    if not funder:
        raise HTTPException(status_code=404, detail="Financiador no encontrado")
    return funder


@router.get("/funders/{funder_id}/budget-lines", response_model=list[BudgetLineTemplateResponse])
def list_funder_templates(
    funder_id: int,
    user: User = Depends(require_permission(Permiso.presupuesto_ver)),
    service: BudgetService = Depends(get_service),
):
    """List budget line templates for a funder"""
    funder = service.get_funder_by_id(funder_id)
    if not funder:
        raise HTTPException(status_code=404, detail="Financiador no encontrado")
    return service.get_funder_templates(funder_id)


@router.get("/projects/{project_id}/budget", response_model=BudgetSummary)
def get_project_budget(
    project_id: int,
    user: User = Depends(require_permission(Permiso.presupuesto_ver)),
    service: BudgetService = Depends(get_service),
):
    """Get budget summary for a project"""
    return service.get_project_budget_summary(project_id)


@router.post("/projects/{project_id}/budget/initialize", response_model=list[ProjectBudgetLineResponse])
def initialize_project_budget(
    project_id: int,
    funder_id: int,
    user: User = Depends(require_permission(Permiso.presupuesto_editar)),
    service: BudgetService = Depends(get_service),
):
    """Initialize project budget from funder templates"""
    funder = service.get_funder_by_id(funder_id)
    if not funder:
        raise HTTPException(status_code=404, detail="Financiador no encontrado")

    lines = service.initialize_project_budget(project_id, funder_id)

    return [
        ProjectBudgetLineResponse(
            id=line.id,
            project_id=line.project_id,
            template_id=line.template_id,
            parent_id=line.parent_id,
            code=line.code,
            name=line.name,
            category=line.category,
            is_spain_only=line.is_spain_only,
            order=line.order,
            max_percentage=line.max_percentage,
            aprobado=line.aprobado,
            ejecutado_espana=line.ejecutado_espana,
            ejecutado_terreno=line.ejecutado_terreno,
            total_ejecutado=line.total_ejecutado,
            diferencia=line.diferencia,
            porcentaje_ejecucion=line.porcentaje_ejecucion,
            has_deviation_alert=line.has_deviation_alert,
            created_at=line.created_at,
            updated_at=line.updated_at,
        )
        for line in lines
    ]


@router.put("/projects/{project_id}/budget-lines/{line_id}", response_model=ProjectBudgetLineResponse)
def update_budget_line(
    project_id: int,
    line_id: int,
    data: ProjectBudgetLineUpdate,
    user: User = Depends(require_permission(Permiso.presupuesto_editar)),
    service: BudgetService = Depends(get_service),
):
    """Update a budget line"""
    line = service.get_budget_line_by_id(line_id)
    if not line or line.project_id != project_id:
        raise HTTPException(status_code=404, detail="Partida no encontrada")

    updated = service.update_budget_line(line_id, data)

    return ProjectBudgetLineResponse(
        id=updated.id,
        project_id=updated.project_id,
        template_id=updated.template_id,
        parent_id=updated.parent_id,
        code=updated.code,
        name=updated.name,
        category=updated.category,
        is_spain_only=updated.is_spain_only,
        order=updated.order,
        max_percentage=updated.max_percentage,
        aprobado=updated.aprobado,
        ejecutado_espana=updated.ejecutado_espana,
        ejecutado_terreno=updated.ejecutado_terreno,
        total_ejecutado=updated.total_ejecutado,
        diferencia=updated.diferencia,
        porcentaje_ejecucion=updated.porcentaje_ejecucion,
        has_deviation_alert=updated.has_deviation_alert,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )
