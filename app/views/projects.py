from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import date, datetime
from typing import List
from app.database import get_db
from app.models.project import EstadoProyecto, TipoProyecto, Financiador
from app.models.user import User, Rol
from app.schemas.project import ProjectCreate, ProjectUpdate, PlazoCreate
from app.services.project_service import ProjectService
from app.auth.dependencies import get_current_user, require_permission, check_project_access
from app.auth.permissions import Permiso, user_has_permission
from app.services.audit_service import AuditService
from app.models.audit_log import ActorType, AccionAuditoria

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Add datetime.now to Jinja2 globals
templates.env.globals["now"] = datetime.now


def get_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


def get_common_context(service: ProjectService) -> dict:
    return {
        "estados": list(EstadoProyecto),
        "tipos": list(TipoProyecto),
        "financiadores": list(Financiador),
        "paises": service.get_unique_paises(),
        "sectores": service.get_unique_sectores(),
        "ods_list": service.get_all_ods(),
    }


@router.get("", response_class=HTMLResponse)
def projects_index(
    request: Request,
    page: int = 1,
    estado: str | None = None,
    tipo: str | None = None,
    pais: str | None = None,
    search: str | None = None,
    user: User = Depends(require_permission(Permiso.proyecto_ver)),
    service: ProjectService = Depends(get_service),
):
    estado_enum = EstadoProyecto(estado) if estado else None
    tipo_enum = TipoProyecto(tipo) if tipo else None

    projects, total = service.get_all(
        page=page,
        page_size=20,
        estado=estado_enum,
        tipo=tipo_enum,
        pais=pais,
        search=search,
    )

    # Gestor pais: filter only assigned projects
    if user.rol == Rol.gestor_pais:
        assigned_ids = {p.id for p in user.assigned_projects}
        projects = [p for p in projects if p.id in assigned_ids]
        total = len(projects)

    total_pages = (total + 19) // 20
    stats = service.get_stats()

    return templates.TemplateResponse(
        "pages/projects/index.html",
        {
            "request": request,
            "projects": projects,
            "stats": stats,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "user": user,
            "filters": {
                "estado": estado,
                "tipo": tipo,
                "pais": pais,
                "search": search,
            },
            **get_common_context(service),
        },
    )


@router.get("/new", response_class=HTMLResponse)
def projects_new(
    request: Request,
    user: User = Depends(require_permission(Permiso.proyecto_crear)),
    service: ProjectService = Depends(get_service),
):
    return templates.TemplateResponse(
        "pages/projects/create.html",
        {
            "request": request,
            "user": user,
            **get_common_context(service),
        },
    )


@router.post("/new", response_class=HTMLResponse)
async def projects_create(
    request: Request,
    user: User = Depends(require_permission(Permiso.proyecto_crear)),
    service: ProjectService = Depends(get_service),
):
    form_data = await request.form()

    codigo_contable = form_data.get("codigo_contable")
    codigo_area = form_data.get("codigo_area")
    titulo = form_data.get("titulo")
    pais = form_data.get("pais")
    estado = form_data.get("estado")
    tipo = form_data.get("tipo")
    financiador = form_data.get("financiador")
    sector = form_data.get("sector")
    subvencion = form_data.get("subvencion")
    cuenta_bancaria = form_data.get("cuenta_bancaria") or None
    fecha_inicio = form_data.get("fecha_inicio")
    fecha_finalizacion = form_data.get("fecha_finalizacion")
    fecha_justificacion = form_data.get("fecha_justificacion") or None
    ampliado = form_data.get("ampliado") == "true"

    # Parse ODS from form (checkboxes)
    ods_ids = [int(x) for x in form_data.getlist("ods_ids[]")]

    # Parse plazos from form
    plazos = []
    plazo_titulos = form_data.getlist("plazo_titulo[]")
    plazo_fechas = form_data.getlist("plazo_fecha[]")

    for i, (plazo_titulo, plazo_fecha) in enumerate(zip(plazo_titulos, plazo_fechas)):
        if plazo_titulo and plazo_fecha:
            plazos.append(PlazoCreate(
                titulo=plazo_titulo,
                fecha_limite=date.fromisoformat(plazo_fecha),
                completado=False
            ))

    # Check for duplicate
    existing = service.get_by_codigo_contable(codigo_contable)
    if existing:
        return templates.TemplateResponse(
            "pages/projects/create.html",
            {
                "request": request,
                "error": f"Ya existe un proyecto con código contable {codigo_contable}",
                **get_common_context(service),
            },
            status_code=400,
        )

    data = ProjectCreate(
        codigo_contable=codigo_contable,
        codigo_area=codigo_area,
        titulo=titulo,
        pais=pais,
        estado=EstadoProyecto(estado),
        tipo=TipoProyecto(tipo),
        financiador=Financiador(financiador),
        sector=sector,
        subvencion=Decimal(subvencion.replace(",", ".")),
        cuenta_bancaria=cuenta_bancaria,
        fecha_inicio=date.fromisoformat(fecha_inicio),
        fecha_finalizacion=date.fromisoformat(fecha_finalizacion),
        fecha_justificacion=date.fromisoformat(fecha_justificacion) if fecha_justificacion else None,
        ampliado=ampliado,
        plazos=plazos,
        ods_ids=ods_ids,
    )
    project = service.create(data)

    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=user.id,
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.create,
        recurso="project",
        recurso_id=str(project.id),
        detalle={"titulo": project.titulo, "codigo": project.codigo_contable},
        ip_address=request.client.host if request.client else None,
        project_id=project.id,
    )

    return RedirectResponse(url=f"/projects/{project.id}", status_code=303)


@router.get("/{project_id}", response_class=HTMLResponse)
def projects_detail(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.proyecto_ver)),
    _access: User = Depends(check_project_access),
    service: ProjectService = Depends(get_service),
):
    project = service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    # Calculate justification deadline alert for Diputación projects
    justification_alert = None
    if project.financiador == Financiador.diputacion_malaga and project.fecha_justificacion:
        days_until = (project.fecha_justificacion - date.today()).days
        if days_until <= 30:
            if days_until < 0:
                justification_alert = {
                    "type": "error",
                    "days": abs(days_until),
                    "message": f"El plazo de justificacion vencio hace {abs(days_until)} dias",
                }
            elif days_until == 0:
                justification_alert = {
                    "type": "error",
                    "days": 0,
                    "message": "El plazo de justificacion vence HOY",
                }
            else:
                justification_alert = {
                    "type": "warning",
                    "days": days_until,
                    "message": f"Faltan {days_until} dias para el plazo de justificacion",
                }

    return templates.TemplateResponse(
        "pages/projects/detail.html",
        {
            "request": request,
            "project": project,
            "user": user,
            "justification_alert": justification_alert,
            **get_common_context(service),
        },
    )


@router.get("/{project_id}/edit", response_class=HTMLResponse)
def projects_edit(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.proyecto_editar)),
    _access: User = Depends(check_project_access),
    service: ProjectService = Depends(get_service),
):
    project = service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    return templates.TemplateResponse(
        "pages/projects/edit.html",
        {
            "request": request,
            "project": project,
            **get_common_context(service),
        },
    )


@router.post("/{project_id}/edit", response_class=HTMLResponse)
async def projects_update(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.proyecto_editar)),
    service: ProjectService = Depends(get_service),
):
    form_data = await request.form()

    codigo_contable = form_data.get("codigo_contable")
    codigo_area = form_data.get("codigo_area")
    titulo = form_data.get("titulo")
    pais = form_data.get("pais")
    estado = form_data.get("estado")
    tipo = form_data.get("tipo")
    financiador = form_data.get("financiador")
    sector = form_data.get("sector")
    subvencion = form_data.get("subvencion")
    cuenta_bancaria = form_data.get("cuenta_bancaria") or None
    fecha_inicio = form_data.get("fecha_inicio")
    fecha_finalizacion = form_data.get("fecha_finalizacion")
    fecha_justificacion = form_data.get("fecha_justificacion") or None
    ampliado = form_data.get("ampliado") == "true"

    # Parse ODS from form (checkboxes)
    ods_ids = [int(x) for x in form_data.getlist("ods_ids[]")]

    # Check for duplicate on different project
    existing = service.get_by_codigo_contable(codigo_contable)
    if existing and existing.id != project_id:
        project = service.get_by_id(project_id)
        return templates.TemplateResponse(
            "pages/projects/edit.html",
            {
                "request": request,
                "project": project,
                "error": f"Ya existe un proyecto con código contable {codigo_contable}",
                **get_common_context(service),
            },
            status_code=400,
        )

    data = ProjectUpdate(
        codigo_contable=codigo_contable,
        codigo_area=codigo_area,
        titulo=titulo,
        pais=pais,
        estado=EstadoProyecto(estado),
        tipo=TipoProyecto(tipo),
        financiador=Financiador(financiador),
        sector=sector,
        subvencion=Decimal(subvencion.replace(",", ".")),
        cuenta_bancaria=cuenta_bancaria,
        fecha_inicio=date.fromisoformat(fecha_inicio),
        fecha_finalizacion=date.fromisoformat(fecha_finalizacion),
        fecha_justificacion=date.fromisoformat(fecha_justificacion) if fecha_justificacion else None,
        ampliado=ampliado,
        ods_ids=ods_ids,
    )
    service.update(project_id, data)

    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=user.id,
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.update,
        recurso="project",
        recurso_id=str(project_id),
        detalle={"titulo": titulo},
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@router.delete("/{project_id}", response_class=HTMLResponse)
def projects_delete(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.proyecto_eliminar)),
    service: ProjectService = Depends(get_service),
):
    project = service.get_by_id(project_id)
    if not service.delete(project_id):
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=user.id,
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.delete,
        recurso="project",
        recurso_id=str(project_id),
        detalle={"titulo": project.titulo if project else None},
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    return HTMLResponse(content="", status_code=200)


# Plazo endpoints
@router.post("/{project_id}/plazos", response_class=HTMLResponse)
def add_plazo(
    request: Request,
    project_id: int,
    plazo_titulo: str = Form(...),
    plazo_fecha: date = Form(...),
    service: ProjectService = Depends(get_service),
):
    plazo_data = PlazoCreate(titulo=plazo_titulo, fecha_limite=plazo_fecha)
    plazo = service.add_plazo(project_id, plazo_data)
    if not plazo:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    project = service.get_by_id(project_id)
    return templates.TemplateResponse(
        "partials/projects/plazos_list.html",
        {
            "request": request,
            "project": project,
        },
    )


@router.post("/plazos/{plazo_id}/toggle", response_class=HTMLResponse)
def toggle_plazo(
    request: Request,
    plazo_id: int,
    service: ProjectService = Depends(get_service),
):
    plazo = service.toggle_plazo(plazo_id)
    if not plazo:
        raise HTTPException(status_code=404, detail="Plazo no encontrado")

    project = service.get_by_id(plazo.project_id)
    return templates.TemplateResponse(
        "partials/projects/plazos_list.html",
        {
            "request": request,
            "project": project,
        },
    )


@router.delete("/plazos/{plazo_id}", response_class=HTMLResponse)
def delete_plazo(
    request: Request,
    plazo_id: int,
    service: ProjectService = Depends(get_service),
):
    from app.models.project import Plazo
    plazo_obj = service.db.get(Plazo, plazo_id)
    if not plazo_obj:
        raise HTTPException(status_code=404, detail="Plazo no encontrado")

    project_id = plazo_obj.project_id
    service.delete_plazo(plazo_id)

    project = service.get_by_id(project_id)
    return templates.TemplateResponse(
        "partials/projects/plazos_list.html",
        {
            "request": request,
            "project": project,
        },
    )


# Partials for htmx
@router.get("/partials/list", response_class=HTMLResponse)
def projects_partial_list(
    request: Request,
    page: int = 1,
    estado: str | None = None,
    tipo: str | None = None,
    pais: str | None = None,
    search: str | None = None,
    service: ProjectService = Depends(get_service),
):
    estado_enum = EstadoProyecto(estado) if estado else None
    tipo_enum = TipoProyecto(tipo) if tipo else None

    projects, total = service.get_all(
        page=page,
        page_size=20,
        estado=estado_enum,
        tipo=tipo_enum,
        pais=pais,
        search=search,
    )
    total_pages = (total + 19) // 20

    return templates.TemplateResponse(
        "partials/projects/list.html",
        {
            "request": request,
            "projects": projects,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "filters": {
                "estado": estado,
                "tipo": tipo,
                "pais": pais,
                "search": search,
            },
        },
    )


@router.get("/partials/row/{project_id}", response_class=HTMLResponse)
def projects_partial_row(
    request: Request,
    project_id: int,
    service: ProjectService = Depends(get_service),
):
    project = service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    return templates.TemplateResponse(
        "partials/projects/row.html",
        {
            "request": request,
            "project": project,
        },
    )


@router.get("/partials/stats", response_class=HTMLResponse)
def projects_partial_stats(
    request: Request,
    service: ProjectService = Depends(get_service),
):
    stats = service.get_stats()
    return templates.TemplateResponse(
        "partials/projects/stats.html",
        {
            "request": request,
            "stats": stats,
        },
    )
