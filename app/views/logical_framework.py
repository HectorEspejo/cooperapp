from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date
from app.database import get_db
from app.models.user import User
from app.services.logical_framework_service import LogicalFrameworkService
from app.services.project_service import ProjectService
from app.models.logical_framework import EstadoActividad
from app.schemas.logical_framework import (
    LogicalFrameworkUpdate,
    SpecificObjectiveCreate, SpecificObjectiveUpdate,
    ResultCreate, ResultUpdate,
    ActivityCreate, ActivityUpdate,
    IndicatorCreate, IndicatorUpdate, IndicatorUpdateCreate
)
from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import Permiso
from app.services.audit_service import AuditService
from app.models.audit_log import ActorType, AccionAuditoria

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_service(db: Session = Depends(get_db)) -> LogicalFrameworkService:
    return LogicalFrameworkService(db)


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


# ======================== Main Tab View ========================

@router.get("/{project_id}/marco-logico", response_class=HTMLResponse)
def marco_logico_tab(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.marco_ver)),
    service: LogicalFrameworkService = Depends(get_service),
    project_service: ProjectService = Depends(get_project_service)
):
    """Main Marco Logico tab content (lazy loaded)"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    framework = service.get_framework_by_project(project_id)
    summary = service.get_framework_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html",
        {
            "request": request,
            "project": project,
            "framework": framework,
            "summary": summary,
            "estados_actividad": list(EstadoActividad),
        }
    )


# ======================== Framework Views ========================

@router.post("/{project_id}/marco-logico", response_class=HTMLResponse)
def update_objetivo_general(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.marco_editar)),
    objetivo_general: str = Form(""),
    service: LogicalFrameworkService = Depends(get_service),
    project_service: ProjectService = Depends(get_project_service)
):
    """Update the general objective"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    data = LogicalFrameworkUpdate(objetivo_general=objetivo_general or None)
    service.create_or_update_framework(project_id, data)

    # Audit log
    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.update,
        recurso="logical_framework",
        recurso_id=str(project_id),
        detalle={"campo": "objetivo_general"},
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    framework = service.get_framework_by_project(project_id)
    summary = service.get_framework_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html",
        {
            "request": request,
            "project": project,
            "framework": framework,
            "summary": summary,
            "estados_actividad": list(EstadoActividad),
        }
    )


@router.get("/{project_id}/marco-logico/summary", response_class=HTMLResponse)
def get_summary(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.marco_ver)),
    service: LogicalFrameworkService = Depends(get_service)
):
    """Get summary stats partial"""
    summary = service.get_framework_summary(project_id)
    return templates.TemplateResponse(
        "partials/projects/marco_logico_summary.html",
        {
            "request": request,
            "project_id": project_id,
            "summary": summary,
        }
    )


@router.get("/{project_id}/marco-logico/tree", response_class=HTMLResponse)
def get_tree(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.marco_ver)),
    service: LogicalFrameworkService = Depends(get_service)
):
    """Get the hierarchical tree partial"""
    framework = service.get_framework_by_project(project_id)
    return templates.TemplateResponse(
        "partials/projects/marco_logico_tree.html",
        {
            "request": request,
            "project_id": project_id,
            "framework": framework,
            "estados_actividad": list(EstadoActividad),
        }
    )


# ======================== Objective Views ========================

@router.get("/{project_id}/marco-logico/objective-form", response_class=HTMLResponse)
def get_objective_form(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.marco_ver)),
    objective_id: int | None = None,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Get the form for creating or editing an objective"""
    framework = service.get_framework_by_project(project_id)
    objective = None
    mode = "create"

    if objective_id:
        objective = service.get_objective(objective_id)
        if not objective:
            raise HTTPException(status_code=404, detail="Objetivo no encontrado")
        mode = "edit"

    next_numero = len(framework.specific_objectives) + 1 if framework else 1

    return templates.TemplateResponse(
        "partials/projects/marco_logico_objective_form.html",
        {
            "request": request,
            "project_id": project_id,
            "objective": objective,
            "mode": mode,
            "next_numero": next_numero,
        }
    )


@router.post("/{project_id}/marco-logico/objectives", response_class=HTMLResponse)
def add_objective(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.marco_editar)),
    numero: int = Form(...),
    descripcion: str = Form(...),
    service: LogicalFrameworkService = Depends(get_service),
    project_service: ProjectService = Depends(get_project_service)
):
    """Add a specific objective"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    data = SpecificObjectiveCreate(numero=numero, descripcion=descripcion)
    service.add_objective(project_id, data)

    # Audit log
    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.create,
        recurso="specific_objective",
        recurso_id=None,
        detalle={"descripcion": descripcion[:100]},
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    framework = service.get_framework_by_project(project_id)
    summary = service.get_framework_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html",
        {
            "request": request,
            "project": project,
            "framework": framework,
            "summary": summary,
            "estados_actividad": list(EstadoActividad),
        }
    )


@router.put("/objectives/{objective_id}", response_class=HTMLResponse)
async def update_objective(
    request: Request,
    objective_id: int,
    user: User = Depends(require_permission(Permiso.marco_editar)),
    service: LogicalFrameworkService = Depends(get_service),
    project_service: ProjectService = Depends(get_project_service)
):
    """Update a specific objective"""
    form_data = await request.form()

    objective = service.get_objective(objective_id)
    if not objective:
        raise HTTPException(status_code=404, detail="Objetivo no encontrado")

    numero = form_data.get("numero")
    descripcion = form_data.get("descripcion")

    data = SpecificObjectiveUpdate()
    if numero:
        data.numero = int(numero)
    if descripcion:
        data.descripcion = descripcion

    service.update_objective(objective_id, data)

    # Audit log
    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.update,
        recurso="specific_objective",
        recurso_id=str(objective_id),
        detalle=None,
        ip_address=request.client.host if request.client else None,
    )

    # Get project_id from objective's framework
    objective = service.get_objective(objective_id)
    framework = service.get_framework_by_project(objective.framework.project_id)
    project = project_service.get_by_id(objective.framework.project_id)
    summary = service.get_framework_summary(objective.framework.project_id)

    return templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html",
        {
            "request": request,
            "project": project,
            "framework": framework,
            "summary": summary,
            "estados_actividad": list(EstadoActividad),
        }
    )


@router.delete("/objectives/{objective_id}", response_class=HTMLResponse)
def delete_objective(
    request: Request,
    objective_id: int,
    user: User = Depends(require_permission(Permiso.marco_editar)),
    service: LogicalFrameworkService = Depends(get_service),
    project_service: ProjectService = Depends(get_project_service)
):
    """Delete a specific objective"""
    objective = service.get_objective(objective_id)
    if not objective:
        raise HTTPException(status_code=404, detail="Objetivo no encontrado")

    project_id = objective.framework.project_id
    service.delete_objective(objective_id)

    # Audit log
    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.delete,
        recurso="specific_objective",
        recurso_id=str(objective_id),
        detalle=None,
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    framework = service.get_framework_by_project(project_id)
    project = project_service.get_by_id(project_id)
    summary = service.get_framework_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html",
        {
            "request": request,
            "project": project,
            "framework": framework,
            "summary": summary,
            "estados_actividad": list(EstadoActividad),
        }
    )


# ======================== Result Views ========================

@router.get("/{project_id}/marco-logico/result-form", response_class=HTMLResponse)
def get_result_form(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.marco_ver)),
    objective_id: int | None = None,
    result_id: int | None = None,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Get the form for creating or editing a result"""
    framework = service.get_framework_by_project(project_id)
    result = None
    mode = "create"

    if result_id:
        result = service.get_result(result_id)
        if not result:
            raise HTTPException(status_code=404, detail="Resultado no encontrado")
        mode = "edit"
        objective_id = result.objective_id

    # Get objective for context
    objective = service.get_objective(objective_id) if objective_id else None
    next_numero = f"R{len(objective.results) + 1}" if objective else "R1"

    return templates.TemplateResponse(
        "partials/projects/marco_logico_result_form.html",
        {
            "request": request,
            "project_id": project_id,
            "objective_id": objective_id,
            "result": result,
            "mode": mode,
            "next_numero": next_numero,
        }
    )


@router.post("/objectives/{objective_id}/results", response_class=HTMLResponse)
def add_result(
    request: Request,
    objective_id: int,
    user: User = Depends(require_permission(Permiso.marco_editar)),
    numero: str = Form(...),
    descripcion: str = Form(...),
    service: LogicalFrameworkService = Depends(get_service),
    project_service: ProjectService = Depends(get_project_service)
):
    """Add a result to an objective"""
    objective = service.get_objective(objective_id)
    if not objective:
        raise HTTPException(status_code=404, detail="Objetivo no encontrado")

    data = ResultCreate(numero=numero, descripcion=descripcion)
    service.add_result(objective_id, data)

    project_id = objective.framework.project_id

    # Audit log
    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.create,
        recurso="result",
        recurso_id=None,
        detalle={"descripcion": descripcion[:100]},
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )
    framework = service.get_framework_by_project(project_id)
    project = project_service.get_by_id(project_id)
    summary = service.get_framework_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html",
        {
            "request": request,
            "project": project,
            "framework": framework,
            "summary": summary,
            "estados_actividad": list(EstadoActividad),
        }
    )


@router.put("/results/{result_id}", response_class=HTMLResponse)
async def update_result(
    request: Request,
    result_id: int,
    user: User = Depends(require_permission(Permiso.marco_editar)),
    service: LogicalFrameworkService = Depends(get_service),
    project_service: ProjectService = Depends(get_project_service)
):
    """Update a result"""
    form_data = await request.form()

    result = service.get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Resultado no encontrado")

    data = ResultUpdate()
    if form_data.get("numero"):
        data.numero = form_data.get("numero")
    if form_data.get("descripcion"):
        data.descripcion = form_data.get("descripcion")

    service.update_result(result_id, data)

    # Audit log
    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.update,
        recurso="result",
        recurso_id=str(result_id),
        detalle=None,
        ip_address=request.client.host if request.client else None,
    )

    result = service.get_result(result_id)
    project_id = result.objective.framework.project_id
    framework = service.get_framework_by_project(project_id)
    project = project_service.get_by_id(project_id)
    summary = service.get_framework_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html",
        {
            "request": request,
            "project": project,
            "framework": framework,
            "summary": summary,
            "estados_actividad": list(EstadoActividad),
        }
    )


@router.delete("/results/{result_id}", response_class=HTMLResponse)
def delete_result(
    request: Request,
    result_id: int,
    user: User = Depends(require_permission(Permiso.marco_editar)),
    service: LogicalFrameworkService = Depends(get_service),
    project_service: ProjectService = Depends(get_project_service)
):
    """Delete a result"""
    result = service.get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Resultado no encontrado")

    project_id = result.objective.framework.project_id
    service.delete_result(result_id)

    # Audit log
    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.delete,
        recurso="result",
        recurso_id=str(result_id),
        detalle=None,
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    framework = service.get_framework_by_project(project_id)
    project = project_service.get_by_id(project_id)
    summary = service.get_framework_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html",
        {
            "request": request,
            "project": project,
            "framework": framework,
            "summary": summary,
            "estados_actividad": list(EstadoActividad),
        }
    )


# ======================== Activity Views ========================

@router.get("/{project_id}/marco-logico/activity-form", response_class=HTMLResponse)
def get_activity_form(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.marco_ver)),
    result_id: int | None = None,
    activity_id: int | None = None,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Get the form for creating or editing an activity"""
    activity = None
    mode = "create"

    if activity_id:
        activity = service.get_activity(activity_id)
        if not activity:
            raise HTTPException(status_code=404, detail="Actividad no encontrada")
        mode = "edit"
        result_id = activity.result_id

    # Get result for context
    result = service.get_result(result_id) if result_id else None
    next_numero = f"A{result.numero.replace('R', '')}.{len(result.activities) + 1}" if result else "A1.1"

    return templates.TemplateResponse(
        "partials/projects/marco_logico_activity_form.html",
        {
            "request": request,
            "project_id": project_id,
            "result_id": result_id,
            "activity": activity,
            "mode": mode,
            "next_numero": next_numero,
            "estados_actividad": list(EstadoActividad),
        }
    )


@router.post("/results/{result_id}/activities", response_class=HTMLResponse)
def add_activity(
    request: Request,
    result_id: int,
    user: User = Depends(require_permission(Permiso.marco_editar)),
    numero: str = Form(...),
    descripcion: str = Form(...),
    fecha_inicio_prevista: date | None = Form(None),
    fecha_fin_prevista: date | None = Form(None),
    service: LogicalFrameworkService = Depends(get_service),
    project_service: ProjectService = Depends(get_project_service)
):
    """Add an activity to a result"""
    result = service.get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Resultado no encontrado")

    data = ActivityCreate(
        numero=numero,
        descripcion=descripcion,
        fecha_inicio_prevista=fecha_inicio_prevista,
        fecha_fin_prevista=fecha_fin_prevista
    )
    service.add_activity(result_id, data)

    project_id = result.objective.framework.project_id

    # Audit log
    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.create,
        recurso="activity",
        recurso_id=None,
        detalle={"descripcion": descripcion[:100]},
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )
    framework = service.get_framework_by_project(project_id)
    project = project_service.get_by_id(project_id)
    summary = service.get_framework_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html",
        {
            "request": request,
            "project": project,
            "framework": framework,
            "summary": summary,
            "estados_actividad": list(EstadoActividad),
        }
    )


@router.put("/activities/{activity_id}", response_class=HTMLResponse)
async def update_activity(
    request: Request,
    activity_id: int,
    user: User = Depends(require_permission(Permiso.marco_editar)),
    service: LogicalFrameworkService = Depends(get_service),
    project_service: ProjectService = Depends(get_project_service)
):
    """Update an activity"""
    form_data = await request.form()

    activity = service.get_activity(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    data = ActivityUpdate()
    if form_data.get("numero"):
        data.numero = form_data.get("numero")
    if form_data.get("descripcion"):
        data.descripcion = form_data.get("descripcion")
    if form_data.get("fecha_inicio_prevista"):
        data.fecha_inicio_prevista = date.fromisoformat(form_data.get("fecha_inicio_prevista"))
    if form_data.get("fecha_fin_prevista"):
        data.fecha_fin_prevista = date.fromisoformat(form_data.get("fecha_fin_prevista"))
    if form_data.get("fecha_inicio_real"):
        data.fecha_inicio_real = date.fromisoformat(form_data.get("fecha_inicio_real"))
    if form_data.get("fecha_fin_real"):
        data.fecha_fin_real = date.fromisoformat(form_data.get("fecha_fin_real"))
    if form_data.get("estado"):
        data.estado = EstadoActividad(form_data.get("estado"))

    service.update_activity(activity_id, data)

    activity = service.get_activity(activity_id)
    project_id = activity.result.objective.framework.project_id

    # Audit log
    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.update,
        recurso="activity",
        recurso_id=str(activity_id),
        detalle=None,
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    framework = service.get_framework_by_project(project_id)
    project = project_service.get_by_id(project_id)
    summary = service.get_framework_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html",
        {
            "request": request,
            "project": project,
            "framework": framework,
            "summary": summary,
            "estados_actividad": list(EstadoActividad),
        }
    )


@router.post("/activities/{activity_id}/status", response_class=HTMLResponse)
def update_activity_status(
    request: Request,
    activity_id: int,
    user: User = Depends(require_permission(Permiso.marco_editar)),
    estado: EstadoActividad = Form(...),
    service: LogicalFrameworkService = Depends(get_service),
    project_service: ProjectService = Depends(get_project_service)
):
    """Quick update of activity status"""
    activity = service.get_activity(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    data = ActivityUpdate(estado=estado)
    service.update_activity(activity_id, data)

    activity = service.get_activity(activity_id)
    project_id = activity.result.objective.framework.project_id

    # Audit log
    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.status_change,
        recurso="activity",
        recurso_id=str(activity_id),
        detalle={"estado": estado.value},
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )
    framework = service.get_framework_by_project(project_id)
    project = project_service.get_by_id(project_id)
    summary = service.get_framework_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html",
        {
            "request": request,
            "project": project,
            "framework": framework,
            "summary": summary,
            "estados_actividad": list(EstadoActividad),
        }
    )


@router.delete("/activities/{activity_id}", response_class=HTMLResponse)
def delete_activity(
    request: Request,
    activity_id: int,
    user: User = Depends(require_permission(Permiso.marco_editar)),
    service: LogicalFrameworkService = Depends(get_service),
    project_service: ProjectService = Depends(get_project_service)
):
    """Delete an activity"""
    activity = service.get_activity(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    project_id = activity.result.objective.framework.project_id
    service.delete_activity(activity_id)

    # Audit log
    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.delete,
        recurso="activity",
        recurso_id=str(activity_id),
        detalle=None,
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    framework = service.get_framework_by_project(project_id)
    project = project_service.get_by_id(project_id)
    summary = service.get_framework_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html",
        {
            "request": request,
            "project": project,
            "framework": framework,
            "summary": summary,
            "estados_actividad": list(EstadoActividad),
        }
    )


# ======================== Indicator Views ========================

@router.get("/{project_id}/marco-logico/indicator-form", response_class=HTMLResponse)
def get_indicator_form(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.marco_ver)),
    framework_id: int | None = None,
    objective_id: int | None = None,
    result_id: int | None = None,
    activity_id: int | None = None,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Get the indicator form for adding an indicator at any level"""
    framework = service.get_framework_by_project(project_id)
    next_code = service.get_next_indicator_code(framework.id) if framework else "IOV1"

    return templates.TemplateResponse(
        "partials/projects/marco_logico_indicator_form.html",
        {
            "request": request,
            "project_id": project_id,
            "framework_id": framework_id or (framework.id if framework else None),
            "objective_id": objective_id,
            "result_id": result_id,
            "activity_id": activity_id,
            "next_code": next_code,
            "indicator": None,
            "mode": "create",
        }
    )


@router.post("/{project_id}/marco-logico/indicators", response_class=HTMLResponse)
async def create_indicator(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.marco_editar)),
    service: LogicalFrameworkService = Depends(get_service),
    project_service: ProjectService = Depends(get_project_service)
):
    """Create a new indicator"""
    form_data = await request.form()

    framework = service.get_framework_by_project(project_id)
    if not framework:
        # Create framework if it doesn't exist
        service.create_or_update_framework(project_id, LogicalFrameworkUpdate())
        framework = service.get_framework_by_project(project_id)

    objective_id = form_data.get("objective_id")
    result_id = form_data.get("result_id")
    activity_id = form_data.get("activity_id")

    data = IndicatorCreate(
        framework_id=framework.id,
        objective_id=int(objective_id) if objective_id else None,
        result_id=int(result_id) if result_id else None,
        activity_id=int(activity_id) if activity_id else None,
        codigo=form_data.get("codigo"),
        descripcion=form_data.get("descripcion"),
        unidad_medida=form_data.get("unidad_medida") or None,
        fuente_verificacion=form_data.get("fuente_verificacion") or None,
        valor_base=form_data.get("valor_base") or None,
        valor_meta=form_data.get("valor_meta") or None,
        valor_actual=form_data.get("valor_actual") or None,
    )
    service.create_indicator(data)

    # Audit log
    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.create,
        recurso="indicator",
        recurso_id=None,
        detalle={"codigo": data.codigo},
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    framework = service.get_framework_by_project(project_id)
    project = project_service.get_by_id(project_id)
    summary = service.get_framework_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html",
        {
            "request": request,
            "project": project,
            "framework": framework,
            "summary": summary,
            "estados_actividad": list(EstadoActividad),
        }
    )


@router.get("/indicators/{indicator_id}/edit", response_class=HTMLResponse)
def get_indicator_edit_form(
    request: Request,
    indicator_id: int,
    user: User = Depends(require_permission(Permiso.marco_ver)),
    service: LogicalFrameworkService = Depends(get_service)
):
    """Get the indicator edit form"""
    indicator = service.get_indicator(indicator_id)
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")

    return templates.TemplateResponse(
        "partials/projects/marco_logico_indicator_form.html",
        {
            "request": request,
            "project_id": indicator.framework.project_id,
            "framework_id": indicator.framework_id,
            "objective_id": indicator.objective_id,
            "result_id": indicator.result_id,
            "activity_id": indicator.activity_id,
            "indicator": indicator,
            "mode": "edit",
        }
    )


@router.put("/indicators/{indicator_id}", response_class=HTMLResponse)
async def update_indicator(
    request: Request,
    indicator_id: int,
    user: User = Depends(require_permission(Permiso.marco_editar)),
    service: LogicalFrameworkService = Depends(get_service),
    project_service: ProjectService = Depends(get_project_service)
):
    """Update an indicator"""
    form_data = await request.form()

    indicator = service.get_indicator(indicator_id)
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")

    data = IndicatorUpdate(
        codigo=form_data.get("codigo"),
        descripcion=form_data.get("descripcion"),
        unidad_medida=form_data.get("unidad_medida") or None,
        fuente_verificacion=form_data.get("fuente_verificacion") or None,
        valor_base=form_data.get("valor_base") or None,
        valor_meta=form_data.get("valor_meta") or None,
    )
    service.update_indicator(indicator_id, data)

    project_id = indicator.framework.project_id

    # Audit log
    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.update,
        recurso="indicator",
        recurso_id=str(indicator_id),
        detalle=None,
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )
    framework = service.get_framework_by_project(project_id)
    project = project_service.get_by_id(project_id)
    summary = service.get_framework_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html",
        {
            "request": request,
            "project": project,
            "framework": framework,
            "summary": summary,
            "estados_actividad": list(EstadoActividad),
        }
    )


@router.get("/indicators/{indicator_id}/update-form", response_class=HTMLResponse)
def get_indicator_update_form(
    request: Request,
    indicator_id: int,
    user: User = Depends(require_permission(Permiso.marco_ver)),
    service: LogicalFrameworkService = Depends(get_service)
):
    """Get the form to update indicator value"""
    indicator = service.get_indicator(indicator_id)
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")

    return templates.TemplateResponse(
        "partials/projects/marco_logico_indicator_update_form.html",
        {
            "request": request,
            "indicator": indicator,
        }
    )


@router.post("/indicators/{indicator_id}/update-value", response_class=HTMLResponse)
def update_indicator_value(
    request: Request,
    indicator_id: int,
    user: User = Depends(require_permission(Permiso.marco_editar)),
    valor_nuevo: str = Form(...),
    observaciones: str = Form(""),
    updated_by: str = Form(""),
    service: LogicalFrameworkService = Depends(get_service),
    project_service: ProjectService = Depends(get_project_service)
):
    """Update indicator value with audit log"""
    indicator = service.get_indicator(indicator_id)
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")

    data = IndicatorUpdateCreate(
        valor_nuevo=valor_nuevo,
        observaciones=observaciones or None,
        updated_by=updated_by or None
    )
    service.update_indicator_value(indicator_id, data)

    project_id = indicator.framework.project_id

    # Audit log
    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.update,
        recurso="indicator",
        recurso_id=str(indicator_id),
        detalle={"valor_nuevo": valor_nuevo},
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )
    framework = service.get_framework_by_project(project_id)
    project = project_service.get_by_id(project_id)
    summary = service.get_framework_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html",
        {
            "request": request,
            "project": project,
            "framework": framework,
            "summary": summary,
            "estados_actividad": list(EstadoActividad),
        }
    )


@router.get("/indicators/{indicator_id}/history", response_class=HTMLResponse)
def get_indicator_history(
    request: Request,
    indicator_id: int,
    user: User = Depends(require_permission(Permiso.marco_ver)),
    service: LogicalFrameworkService = Depends(get_service)
):
    """Get the history modal for an indicator"""
    indicator = service.get_indicator(indicator_id)
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")

    history = service.get_indicator_history(indicator_id)

    return templates.TemplateResponse(
        "partials/projects/marco_logico_history_modal.html",
        {
            "request": request,
            "indicator": indicator,
            "history": history,
        }
    )


@router.delete("/indicators/{indicator_id}", response_class=HTMLResponse)
def delete_indicator(
    request: Request,
    indicator_id: int,
    user: User = Depends(require_permission(Permiso.marco_editar)),
    service: LogicalFrameworkService = Depends(get_service),
    project_service: ProjectService = Depends(get_project_service)
):
    """Delete an indicator"""
    indicator = service.get_indicator(indicator_id)
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")

    project_id = indicator.framework.project_id
    service.delete_indicator(indicator_id)

    # Audit log
    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.delete,
        recurso="indicator",
        recurso_id=str(indicator_id),
        detalle=None,
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    framework = service.get_framework_by_project(project_id)
    project = project_service.get_by_id(project_id)
    summary = service.get_framework_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html",
        {
            "request": request,
            "project": project,
            "framework": framework,
            "summary": summary,
            "estados_actividad": list(EstadoActividad),
        }
    )
