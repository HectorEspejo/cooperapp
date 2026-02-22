from decimal import Decimal
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.budget import CategoriaPartida
from app.models.user import User
from app.services.budget_service import BudgetService
from app.auth.dependencies import get_current_user
from app.services.audit_service import AuditService
from app.models.audit_log import ActorType, AccionAuditoria

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_service(db: Session = Depends(get_db)) -> BudgetService:
    return BudgetService(db)


# 1. GET /plantillas-presupuesto - Pagina principal
@router.get("/plantillas-presupuesto", response_class=HTMLResponse)
def budget_templates_index(
    request: Request,
    user: User = Depends(get_current_user),
    service: BudgetService = Depends(get_service),
):
    funders = service.get_all_funders()
    funders_data = []
    for funder in funders:
        versions = service.get_funder_versions(funder.id)
        project_count = service.get_funder_project_count(funder.id)
        versions_data = []
        for v in versions:
            v_project_count = service.get_version_project_count(v.id)
            v_is_editable = service.version_is_editable(v.id)
            lines = service.get_version_lines(v.id)
            versions_data.append({
                "version": v,
                "project_count": v_project_count,
                "is_editable": v_is_editable,
                "line_count": len(lines),
            })
        funders_data.append({
            "funder": funder,
            "versions": versions_data,
            "project_count": project_count,
        })

    return templates.TemplateResponse(
        "pages/budget_templates/index.html",
        {
            "request": request,
            "user": user,
            "funders_data": funders_data,
            "categorias": list(CategoriaPartida),
        },
    )


# 2. POST /plantillas-presupuesto/financiadores - Crear financiador
@router.post("/plantillas-presupuesto/financiadores", response_class=HTMLResponse)
async def create_funder(
    request: Request,
    user: User = Depends(get_current_user),
    service: BudgetService = Depends(get_service),
):
    form_data = await request.form()
    code = form_data.get("code", "").strip().upper()
    name = form_data.get("name", "").strip()
    color = form_data.get("color", "").strip() or None
    max_indirect = form_data.get("max_indirect_percentage", "").strip()
    max_personnel = form_data.get("max_personnel_percentage", "").strip()
    min_audit = form_data.get("min_amount_for_audit", "").strip()

    if not code or not name:
        raise HTTPException(status_code=400, detail="Codigo y nombre son obligatorios")

    existing = service.get_funder_by_code(code)
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un financiador con codigo {code}")

    funder = service.create_funder(
        code=code,
        name=name,
        color=color,
        max_indirect_pct=Decimal(max_indirect) if max_indirect else None,
        max_personnel_pct=Decimal(max_personnel) if max_personnel else None,
        min_audit=Decimal(min_audit) if min_audit else None,
    )

    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=user.id,
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.create,
        recurso="funder",
        recurso_id=str(funder.id),
        detalle={"code": funder.code, "name": funder.name},
        ip_address=request.client.host if request.client else None,
    )

    # Return the updated funder card
    versions = service.get_funder_versions(funder.id)
    return templates.TemplateResponse(
        "partials/budget_templates/funder_card.html",
        {
            "request": request,
            "user": user,
            "funder_data": {
                "funder": funder,
                "versions": [],
                "project_count": 0,
            },
            "categorias": list(CategoriaPartida),
            "is_new": True,
        },
    )


# 3. GET /plantillas-presupuesto/financiadores/{id}/editar - Form editar financiador
@router.get("/plantillas-presupuesto/financiadores/{funder_id}/editar", response_class=HTMLResponse)
def edit_funder_form(
    request: Request,
    funder_id: int,
    user: User = Depends(get_current_user),
    service: BudgetService = Depends(get_service),
):
    funder = service.get_funder_by_id(funder_id)
    if not funder:
        raise HTTPException(status_code=404, detail="Financiador no encontrado")

    return templates.TemplateResponse(
        "partials/budget_templates/funder_form.html",
        {
            "request": request,
            "funder": funder,
            "is_edit": True,
        },
    )


# 4. PUT /plantillas-presupuesto/financiadores/{id} - Actualizar financiador
@router.put("/plantillas-presupuesto/financiadores/{funder_id}", response_class=HTMLResponse)
async def update_funder(
    request: Request,
    funder_id: int,
    user: User = Depends(get_current_user),
    service: BudgetService = Depends(get_service),
):
    form_data = await request.form()
    code = form_data.get("code", "").strip().upper()
    name = form_data.get("name", "").strip()
    color = form_data.get("color", "").strip() or None
    max_indirect = form_data.get("max_indirect_percentage", "").strip()
    max_personnel = form_data.get("max_personnel_percentage", "").strip()
    min_audit = form_data.get("min_amount_for_audit", "").strip()

    funder = service.update_funder(
        funder_id,
        code=code,
        name=name,
        color=color,
        max_indirect_percentage=Decimal(max_indirect) if max_indirect else None,
        max_personnel_percentage=Decimal(max_personnel) if max_personnel else None,
        min_amount_for_audit=Decimal(min_audit) if min_audit else None,
    )
    if not funder:
        raise HTTPException(status_code=404, detail="Financiador no encontrado")

    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=user.id,
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.update,
        recurso="funder",
        recurso_id=str(funder.id),
        detalle={"code": funder.code, "name": funder.name},
        ip_address=request.client.host if request.client else None,
    )

    versions = service.get_funder_versions(funder.id)
    project_count = service.get_funder_project_count(funder.id)
    versions_data = []
    for v in versions:
        v_project_count = service.get_version_project_count(v.id)
        v_is_editable = service.version_is_editable(v.id)
        lines = service.get_version_lines(v.id)
        versions_data.append({
            "version": v,
            "project_count": v_project_count,
            "is_editable": v_is_editable,
            "line_count": len(lines),
        })

    return templates.TemplateResponse(
        "partials/budget_templates/funder_card.html",
        {
            "request": request,
            "user": user,
            "funder_data": {
                "funder": funder,
                "versions": versions_data,
                "project_count": project_count,
            },
            "categorias": list(CategoriaPartida),
        },
    )


# 5. DELETE /plantillas-presupuesto/financiadores/{id} - Eliminar financiador
@router.delete("/plantillas-presupuesto/financiadores/{funder_id}", response_class=HTMLResponse)
def delete_funder(
    request: Request,
    funder_id: int,
    user: User = Depends(get_current_user),
    service: BudgetService = Depends(get_service),
):
    funder = service.get_funder_by_id(funder_id)
    if not funder:
        raise HTTPException(status_code=404, detail="Financiador no encontrado")

    try:
        service.delete_funder(funder_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=user.id,
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.delete,
        recurso="funder",
        recurso_id=str(funder_id),
        detalle={"code": funder.code, "name": funder.name},
        ip_address=request.client.host if request.client else None,
    )

    return HTMLResponse(content="", status_code=200)


# 6. GET /plantillas-presupuesto/versiones/{id} - Detalle de version
@router.get("/plantillas-presupuesto/versiones/{version_id}", response_class=HTMLResponse)
def version_detail(
    request: Request,
    version_id: int,
    user: User = Depends(get_current_user),
    service: BudgetService = Depends(get_service),
):
    version = service.get_template_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version no encontrada")

    lines = service.get_version_lines(version_id)
    project_count = service.get_version_project_count(version_id)
    is_editable = service.version_is_editable(version_id)
    funder = service.get_funder_by_id(version.funder_id)

    return templates.TemplateResponse(
        "partials/budget_templates/version_detail.html",
        {
            "request": request,
            "user": user,
            "version": version,
            "lines": lines,
            "project_count": project_count,
            "is_editable": is_editable,
            "funder": funder,
            "categorias": list(CategoriaPartida),
        },
    )


# 7. POST /plantillas-presupuesto/financiadores/{id}/versiones - Nueva version
@router.post("/plantillas-presupuesto/financiadores/{funder_id}/versiones", response_class=HTMLResponse)
def create_version(
    request: Request,
    funder_id: int,
    user: User = Depends(get_current_user),
    service: BudgetService = Depends(get_service),
):
    funder = service.get_funder_by_id(funder_id)
    if not funder:
        raise HTTPException(status_code=404, detail="Financiador no encontrado")

    version = service.create_template_version(funder_id)

    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=user.id,
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.create,
        recurso="budget_template_version",
        recurso_id=str(version.id),
        detalle={"funder": funder.code, "version": version.version},
        ip_address=request.client.host if request.client else None,
    )

    lines = service.get_version_lines(version.id)
    project_count = 0

    return templates.TemplateResponse(
        "partials/budget_templates/version_detail.html",
        {
            "request": request,
            "user": user,
            "version": version,
            "lines": lines,
            "project_count": project_count,
            "is_editable": True,
            "funder": funder,
            "categorias": list(CategoriaPartida),
        },
    )


# 8. POST /plantillas-presupuesto/versiones/{id}/clonar - Clonar version
@router.post("/plantillas-presupuesto/versiones/{version_id}/clonar", response_class=HTMLResponse)
def clone_version(
    request: Request,
    version_id: int,
    user: User = Depends(get_current_user),
    service: BudgetService = Depends(get_service),
):
    try:
        new_version = service.clone_template_version(version_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    funder = service.get_funder_by_id(new_version.funder_id)

    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=user.id,
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.create,
        recurso="budget_template_version",
        recurso_id=str(new_version.id),
        detalle={"funder": funder.code, "version": new_version.version, "cloned_from": version_id},
        ip_address=request.client.host if request.client else None,
    )

    lines = service.get_version_lines(new_version.id)

    return templates.TemplateResponse(
        "partials/budget_templates/version_detail.html",
        {
            "request": request,
            "user": user,
            "version": new_version,
            "lines": lines,
            "project_count": 0,
            "is_editable": True,
            "funder": funder,
            "categorias": list(CategoriaPartida),
        },
    )


# 9. PUT /plantillas-presupuesto/versiones/{id}/activa - Toggle is_active
@router.put("/plantillas-presupuesto/versiones/{version_id}/activa", response_class=HTMLResponse)
def toggle_version_active(
    request: Request,
    version_id: int,
    user: User = Depends(get_current_user),
    service: BudgetService = Depends(get_service),
):
    version = service.toggle_version_active(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version no encontrada")

    funder = service.get_funder_by_id(version.funder_id)
    lines = service.get_version_lines(version_id)
    project_count = service.get_version_project_count(version_id)
    is_editable = service.version_is_editable(version_id)

    return templates.TemplateResponse(
        "partials/budget_templates/version_detail.html",
        {
            "request": request,
            "user": user,
            "version": version,
            "lines": lines,
            "project_count": project_count,
            "is_editable": is_editable,
            "funder": funder,
            "categorias": list(CategoriaPartida),
        },
    )


# 10. DELETE /plantillas-presupuesto/versiones/{id} - Eliminar version
@router.delete("/plantillas-presupuesto/versiones/{version_id}", response_class=HTMLResponse)
def delete_version(
    request: Request,
    version_id: int,
    user: User = Depends(get_current_user),
    service: BudgetService = Depends(get_service),
):
    version = service.get_template_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version no encontrada")

    try:
        service.delete_template_version(version_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=user.id,
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.delete,
        recurso="budget_template_version",
        recurso_id=str(version_id),
        detalle={"funder_id": version.funder_id, "version": version.version},
        ip_address=request.client.host if request.client else None,
    )

    return HTMLResponse(content="", status_code=200)


# 11. POST /plantillas-presupuesto/versiones/{id}/lineas - Anadir linea
@router.post("/plantillas-presupuesto/versiones/{version_id}/lineas", response_class=HTMLResponse)
async def add_line(
    request: Request,
    version_id: int,
    user: User = Depends(get_current_user),
    service: BudgetService = Depends(get_service),
):
    form_data = await request.form()
    code = form_data.get("code", "").strip()
    name = form_data.get("name", "").strip()
    category = form_data.get("category", "")
    is_spain_only = form_data.get("is_spain_only") == "true"
    order = int(form_data.get("order", "0"))
    max_pct = form_data.get("max_percentage", "").strip()

    if not code or not name:
        raise HTTPException(status_code=400, detail="Codigo y nombre son obligatorios")

    line = service.add_template_line(
        version_id=version_id,
        code=code,
        name=name,
        category=CategoriaPartida(category),
        is_spain_only=is_spain_only,
        order=order,
        max_pct=Decimal(max_pct) if max_pct else None,
    )

    # Return updated version detail
    version = service.get_template_version(version_id)
    funder = service.get_funder_by_id(version.funder_id)
    lines = service.get_version_lines(version_id)
    project_count = service.get_version_project_count(version_id)
    is_editable = service.version_is_editable(version_id)

    return templates.TemplateResponse(
        "partials/budget_templates/version_detail.html",
        {
            "request": request,
            "user": user,
            "version": version,
            "lines": lines,
            "project_count": project_count,
            "is_editable": is_editable,
            "funder": funder,
            "categorias": list(CategoriaPartida),
        },
    )


# 12. PUT /plantillas-presupuesto/lineas/{id} - Editar linea
@router.put("/plantillas-presupuesto/lineas/{line_id}", response_class=HTMLResponse)
async def update_line(
    request: Request,
    line_id: int,
    user: User = Depends(get_current_user),
    service: BudgetService = Depends(get_service),
):
    form_data = await request.form()
    code = form_data.get("code", "").strip()
    name = form_data.get("name", "").strip()
    category = form_data.get("category", "")
    is_spain_only = form_data.get("is_spain_only") == "true"
    order = int(form_data.get("order", "0"))
    max_pct = form_data.get("max_percentage", "").strip()

    line = service.update_template_line(
        line_id,
        code=code,
        name=name,
        category=CategoriaPartida(category),
        is_spain_only=is_spain_only,
        order=order,
        max_percentage=Decimal(max_pct) if max_pct else None,
    )
    if not line:
        raise HTTPException(status_code=404, detail="Linea no encontrada")

    # Return updated version detail
    version = service.get_template_version(line.template_version_id)
    funder = service.get_funder_by_id(version.funder_id)
    lines = service.get_version_lines(version.id)
    project_count = service.get_version_project_count(version.id)
    is_editable = service.version_is_editable(version.id)

    return templates.TemplateResponse(
        "partials/budget_templates/version_detail.html",
        {
            "request": request,
            "user": user,
            "version": version,
            "lines": lines,
            "project_count": project_count,
            "is_editable": is_editable,
            "funder": funder,
            "categorias": list(CategoriaPartida),
        },
    )


# 13. DELETE /plantillas-presupuesto/lineas/{id} - Eliminar linea
@router.delete("/plantillas-presupuesto/lineas/{line_id}", response_class=HTMLResponse)
def delete_line(
    request: Request,
    line_id: int,
    user: User = Depends(get_current_user),
    service: BudgetService = Depends(get_service),
):
    from app.models.budget import BudgetLineTemplate
    line = service.db.get(BudgetLineTemplate, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Linea no encontrada")

    version_id = line.template_version_id
    service.delete_template_line(line_id)

    # Return updated version detail
    version = service.get_template_version(version_id)
    funder = service.get_funder_by_id(version.funder_id)
    lines = service.get_version_lines(version.id)
    project_count = service.get_version_project_count(version.id)
    is_editable = service.version_is_editable(version.id)

    return templates.TemplateResponse(
        "partials/budget_templates/version_detail.html",
        {
            "request": request,
            "user": user,
            "version": version,
            "lines": lines,
            "project_count": project_count,
            "is_editable": is_editable,
            "funder": funder,
            "categorias": list(CategoriaPartida),
        },
    )


# HTMX endpoint: versiones select options para crear/editar proyecto
@router.get("/plantillas-presupuesto/financiadores/{funder_id}/versiones-select", response_class=HTMLResponse)
def funder_versions_select(
    request: Request,
    funder_id: int,
    service: BudgetService = Depends(get_service),
):
    versions = service.get_active_funder_versions(funder_id)
    funder = service.get_funder_by_id(funder_id)

    options_html = ""
    for v in versions:
        line_count = len(service.get_version_lines(v.id))
        options_html += f'<option value="{v.id}">v{v.version} ({line_count} partidas)</option>\n'

    if not versions:
        options_html = '<option value="">Sin versiones activas</option>'

    # Also return funder info
    info_html = ""
    if funder:
        info_html = f'<strong>{funder.name}</strong><br>'
        if funder.max_indirect_percentage:
            info_html += f'<span class="info-line">Max. indirectos: {funder.max_indirect_percentage}%</span><br>'
        else:
            info_html += '<span class="info-line">Sin limite de costes indirectos</span><br>'
        if funder.max_personnel_percentage:
            info_html += f'<span class="info-line">Max. personal: {funder.max_personnel_percentage}%</span><br>'
        if funder.min_amount_for_audit:
            info_html += f'<span class="info-line">Auditoria obligatoria desde {funder.min_amount_for_audit} EUR</span>'

    return HTMLResponse(content=f"""
        <select id="template_version_id" name="template_version_id" required>
            {options_html}
        </select>
        <div id="funder-info" class="funder-info-tooltip" style="display: block;">{info_html}</div>
    """)
