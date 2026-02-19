from decimal import Decimal
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.funding import TipoFuente
from app.services.budget_service import BudgetService
from app.services.project_service import ProjectService
from app.schemas.budget import ProjectBudgetLineUpdate
from app.auth.dependencies import require_permission
from app.auth.permissions import Permiso
from app.services.audit_service import AuditService
from app.models.audit_log import ActorType, AccionAuditoria

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
    user: User = Depends(require_permission(Permiso.presupuesto_ver)),
    budget_service: BudgetService = Depends(get_budget_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Render the budget tab content"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    budget_summary = budget_service.get_project_budget_summary(project_id)
    funders = budget_service.get_all_funders()
    funding_sources = budget_service.get_project_funding_sources(project_id)
    funding_summary = budget_service.get_funding_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/budget_tab.html",
        {
            "request": request,
            "project": project,
            "budget": budget_summary,
            "funders": funders,
            "funding_sources": funding_sources,
            "funding_summary": funding_summary,
            "user": user,
        },
    )


@router.post("/{project_id}/budget/initialize", response_class=HTMLResponse)
def initialize_budget(
    request: Request,
    project_id: int,
    funder_id: int = Form(...),
    user: User = Depends(require_permission(Permiso.presupuesto_editar)),
    budget_service: BudgetService = Depends(get_budget_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Initialize budget from funder templates"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    budget_service.initialize_project_budget(project_id, funder_id)

    # Audit log
    audit = AuditService(budget_service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.create,
        recurso="budget",
        recurso_id=str(project_id),
        detalle={"funder_id": funder_id},
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    budget_summary = budget_service.get_project_budget_summary(project_id)
    funding_sources = budget_service.get_project_funding_sources(project_id)
    funding_summary = budget_service.get_funding_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/budget_table.html",
        {
            "request": request,
            "project": project,
            "budget": budget_summary,
            "funding_sources": funding_sources,
            "funding_summary": funding_summary,
            "user": user,
        },
    )


@router.put("/{project_id}/budget-lines/{line_id}", response_class=HTMLResponse)
async def update_budget_line(
    request: Request,
    project_id: int,
    line_id: int,
    user: User = Depends(require_permission(Permiso.presupuesto_editar)),
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

    # Audit log
    audit = AuditService(budget_service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.update,
        recurso="budget_line",
        recurso_id=str(line_id),
        detalle={"line_name": line.name if line else None},
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    # Return the entire budget table to update totals
    project = project_service.get_by_id(project_id)
    budget_summary = budget_service.get_project_budget_summary(project_id)
    funding_sources = budget_service.get_project_funding_sources(project_id)
    funding_summary = budget_service.get_funding_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/budget_table.html",
        {
            "request": request,
            "project": project,
            "budget": budget_summary,
            "funding_sources": funding_sources,
            "funding_summary": funding_summary,
            "user": user,
        },
    )


# =============================================
# Funding Sources Endpoints
# =============================================

@router.post("/{project_id}/funding-sources", response_class=HTMLResponse)
async def create_funding_source(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.presupuesto_editar)),
    budget_service: BudgetService = Depends(get_budget_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Create a new funding source for a project"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    form_data = await request.form()
    nombre = form_data.get("nombre", "").strip()
    tipo = form_data.get("tipo", "otro")

    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre es obligatorio")

    try:
        tipo_enum = TipoFuente(tipo)
    except ValueError:
        tipo_enum = TipoFuente.otro

    try:
        budget_service.create_funding_source(project_id, nombre, tipo_enum)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Audit log
    audit = AuditService(budget_service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.create,
        recurso="funding_source",
        recurso_id=str(project_id),
        detalle={"nombre": nombre, "tipo": tipo},
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    # Return updated budget tab
    budget_summary = budget_service.get_project_budget_summary(project_id)
    funding_sources = budget_service.get_project_funding_sources(project_id)
    funding_summary = budget_service.get_funding_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/budget_table.html",
        {
            "request": request,
            "project": project,
            "budget": budget_summary,
            "funding_sources": funding_sources,
            "funding_summary": funding_summary,
            "user": user,
        },
    )


@router.delete("/{project_id}/funding-sources/{source_id}", response_class=HTMLResponse)
def delete_funding_source(
    request: Request,
    project_id: int,
    source_id: int,
    user: User = Depends(require_permission(Permiso.presupuesto_editar)),
    budget_service: BudgetService = Depends(get_budget_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Delete a funding source (only if no expenses are associated)"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    source = budget_service.get_funding_source_by_id(source_id)
    if not source or source.project_id != project_id:
        raise HTTPException(status_code=404, detail="Fuente de financiacion no encontrada")

    try:
        budget_service.delete_funding_source(source_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Audit log
    audit = AuditService(budget_service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.delete,
        recurso="funding_source",
        recurso_id=str(source_id),
        detalle={"nombre": source.nombre},
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    # Return updated budget table
    budget_summary = budget_service.get_project_budget_summary(project_id)
    funding_sources = budget_service.get_project_funding_sources(project_id)
    funding_summary = budget_service.get_funding_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/budget_table.html",
        {
            "request": request,
            "project": project,
            "budget": budget_summary,
            "funding_sources": funding_sources,
            "funding_summary": funding_summary,
            "user": user,
        },
    )


# =============================================
# Budget Line Distribution Endpoints
# =============================================

@router.get("/{project_id}/budget-lines/{line_id}/distribution", response_class=HTMLResponse)
def get_line_distribution(
    request: Request,
    project_id: int,
    line_id: int,
    user: User = Depends(require_permission(Permiso.presupuesto_ver)),
    budget_service: BudgetService = Depends(get_budget_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Get the distribution modal for a budget line"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    line = budget_service.get_budget_line_by_id(line_id)
    if not line or line.project_id != project_id:
        raise HTTPException(status_code=404, detail="Partida no encontrada")

    funding_sources = budget_service.get_project_funding_sources(project_id)
    budget_service.ensure_allocations_for_line(line_id, project_id)
    allocations = budget_service.get_line_distribution(line_id)

    # Build a map source_id -> aprobado
    alloc_map = {a.funding_source_id: a.aprobado for a in allocations}

    return templates.TemplateResponse(
        "partials/projects/budget_line_distribution_modal.html",
        {
            "request": request,
            "project": project,
            "line": line,
            "funding_sources": funding_sources,
            "alloc_map": alloc_map,
            "user": user,
        },
    )


@router.put("/{project_id}/budget-lines/{line_id}/distribution", response_class=HTMLResponse)
async def update_line_distribution(
    request: Request,
    project_id: int,
    line_id: int,
    user: User = Depends(require_permission(Permiso.presupuesto_editar)),
    budget_service: BudgetService = Depends(get_budget_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Save the distribution of a budget line by funding source"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    line = budget_service.get_budget_line_by_id(line_id)
    if not line or line.project_id != project_id:
        raise HTTPException(status_code=404, detail="Partida no encontrada")

    form_data = await request.form()
    funding_sources = budget_service.get_project_funding_sources(project_id)

    allocations = []
    for source in funding_sources:
        field_name = f"source_{source.id}"
        value_str = form_data.get(field_name, "0").replace(",", ".")
        try:
            value = Decimal(value_str) if value_str else Decimal("0")
        except Exception:
            value = Decimal("0")
        allocations.append({
            "funding_source_id": source.id,
            "aprobado": value,
        })

    budget_service.update_line_distribution(line_id, allocations)

    # Audit log
    audit = AuditService(budget_service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.update,
        recurso="budget_line_distribution",
        recurso_id=str(line_id),
        detalle={"line_name": line.name},
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    # Return updated budget table
    budget_summary = budget_service.get_project_budget_summary(project_id)
    funding_sources = budget_service.get_project_funding_sources(project_id)
    funding_summary = budget_service.get_funding_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/budget_table.html",
        {
            "request": request,
            "project": project,
            "budget": budget_summary,
            "funding_sources": funding_sources,
            "funding_summary": funding_summary,
            "user": user,
        },
    )
