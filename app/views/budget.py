from decimal import Decimal
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.budget_service import BudgetService
from app.services.project_service import ProjectService
from app.schemas.budget import ProjectBudgetLineUpdate

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_budget_service(db: Session = Depends(get_db)) -> BudgetService:
    return BudgetService(db)


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


@router.get("/{project_id}/budget", response_class=HTMLResponse)
def budget_tab(
    request: Request,
    project_id: int,
    budget_service: BudgetService = Depends(get_budget_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Render the budget tab content"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    budget_summary = budget_service.get_project_budget_summary(project_id)
    funders = budget_service.get_all_funders()

    return templates.TemplateResponse(
        "partials/projects/budget_tab.html",
        {
            "request": request,
            "project": project,
            "budget": budget_summary,
            "funders": funders,
        },
    )


@router.post("/{project_id}/budget/initialize", response_class=HTMLResponse)
def initialize_budget(
    request: Request,
    project_id: int,
    funder_id: int = Form(...),
    budget_service: BudgetService = Depends(get_budget_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Initialize budget from funder templates"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    budget_service.initialize_project_budget(project_id, funder_id)
    budget_summary = budget_service.get_project_budget_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/budget_table.html",
        {
            "request": request,
            "project": project,
            "budget": budget_summary,
        },
    )


@router.put("/{project_id}/budget-lines/{line_id}", response_class=HTMLResponse)
async def update_budget_line(
    request: Request,
    project_id: int,
    line_id: int,
    budget_service: BudgetService = Depends(get_budget_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Update a budget line and return updated row"""
    form_data = await request.form()

    aprobado = form_data.get("aprobado")
    ejecutado_espana = form_data.get("ejecutado_espana")
    ejecutado_terreno = form_data.get("ejecutado_terreno")

    update_data = ProjectBudgetLineUpdate()
    if aprobado:
        update_data.aprobado = Decimal(aprobado.replace(",", "."))
    if ejecutado_espana:
        update_data.ejecutado_espana = Decimal(ejecutado_espana.replace(",", "."))
    if ejecutado_terreno:
        update_data.ejecutado_terreno = Decimal(ejecutado_terreno.replace(",", "."))

    line = budget_service.get_budget_line_by_id(line_id)
    if not line or line.project_id != project_id:
        raise HTTPException(status_code=404, detail="Partida no encontrada")

    budget_service.update_budget_line(line_id, update_data)

    # Return the entire budget table to update totals
    project = project_service.get_by_id(project_id)
    budget_summary = budget_service.get_project_budget_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/budget_table.html",
        {
            "request": request,
            "project": project,
            "budget": budget_summary,
        },
    )
