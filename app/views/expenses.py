from datetime import date
from decimal import Decimal
import os
from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.expense import UbicacionGasto, EstadoGasto
from app.models.document import CategoriaDocumento
from app.models.user import User
from app.services.expense_service import ExpenseService
from app.services.project_service import ProjectService
from app.services.document_service import DocumentService
from app.schemas.expense import ExpenseCreate, ExpenseUpdate, ExpenseFilters
from app.schemas.document import DocumentCreate
from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import Permiso
from app.services.audit_service import AuditService
from app.models.audit_log import ActorType, AccionAuditoria

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_expense_service(db: Session = Depends(get_db)) -> ExpenseService:
    return ExpenseService(db)


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    return DocumentService(db)


@router.get("/{project_id}/expenses", response_class=HTMLResponse)
def expenses_tab(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.gasto_ver)),
    expense_service: ExpenseService = Depends(get_expense_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Render the expenses tab content"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    expenses = expense_service.get_project_expenses(project_id)
    summary = expense_service.get_expense_summary(project_id)
    budget_lines = expense_service.get_budget_lines_with_balance(project_id)

    return templates.TemplateResponse(
        "partials/projects/expenses_tab.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "expenses": expenses,
            "summary": summary,
            "budget_lines": budget_lines,
            "estados": EstadoGasto,
            "ubicaciones": UbicacionGasto,
        },
    )


@router.get("/{project_id}/expenses/table", response_class=HTMLResponse)
def expenses_table(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.gasto_ver)),
    budget_line_id: int | None = Query(None),
    estado: str | None = Query(None),
    ubicacion: str | None = Query(None),
    fecha_desde: date | None = Query(None),
    fecha_hasta: date | None = Query(None),
    expense_service: ExpenseService = Depends(get_expense_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Render filtered expenses table"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    filters = ExpenseFilters(
        budget_line_id=budget_line_id,
        estado=EstadoGasto(estado) if estado else None,
        ubicacion=UbicacionGasto(ubicacion) if ubicacion else None,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    expenses = expense_service.get_project_expenses(project_id, filters)
    budget_lines = expense_service.get_budget_lines_with_balance(project_id)

    return templates.TemplateResponse(
        "partials/projects/expenses_table.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "expenses": expenses,
            "budget_lines": budget_lines,
        },
    )


@router.get("/{project_id}/expenses/new", response_class=HTMLResponse)
def new_expense_form(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.gasto_crear)),
    expense_service: ExpenseService = Depends(get_expense_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Render new expense form modal"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    budget_lines = expense_service.get_budget_lines_with_balance(project_id)

    return templates.TemplateResponse(
        "partials/projects/expense_form.html",
        {
            "request": request,
            "project": project,
            "expense": None,
            "budget_lines": budget_lines,
            "ubicaciones": UbicacionGasto,
            "is_edit": False,
        },
    )


@router.get("/{project_id}/expenses/{expense_id}/edit", response_class=HTMLResponse)
def edit_expense_form(
    request: Request,
    project_id: int,
    expense_id: int,
    user: User = Depends(require_permission(Permiso.gasto_crear)),
    expense_service: ExpenseService = Depends(get_expense_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Render edit expense form modal"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    expense = expense_service.get_expense_by_id(expense_id)
    if not expense or expense.project_id != project_id:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")

    budget_lines = expense_service.get_budget_lines_with_balance(project_id)

    return templates.TemplateResponse(
        "partials/projects/expense_form.html",
        {
            "request": request,
            "project": project,
            "expense": expense,
            "budget_lines": budget_lines,
            "ubicaciones": UbicacionGasto,
            "is_edit": True,
        },
    )


@router.post("/{project_id}/expenses", response_class=HTMLResponse)
async def create_expense(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.gasto_crear)),
    expense_service: ExpenseService = Depends(get_expense_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Create a new expense and return updated table"""
    form_data = await request.form()

    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    try:
        # Parse form data
        data = ExpenseCreate(
            budget_line_id=int(form_data.get("budget_line_id")),
            fecha_factura=date.fromisoformat(form_data.get("fecha_factura")),
            concepto=form_data.get("concepto"),
            expedidor=form_data.get("expedidor"),
            persona=form_data.get("persona") or None,
            cantidad_original=Decimal(str(form_data.get("cantidad_original", "0")).replace(",", ".")),
            moneda_original=form_data.get("moneda_original", "EUR"),
            tipo_cambio=Decimal(str(form_data.get("tipo_cambio")).replace(",", ".")) if form_data.get("tipo_cambio") else None,
            cantidad_euros=Decimal(str(form_data.get("cantidad_euros", "0")).replace(",", ".")),
            porcentaje=Decimal(str(form_data.get("porcentaje", "100")).replace(",", ".")),
            financiado_por=form_data.get("financiado_por"),
            ubicacion=UbicacionGasto(form_data.get("ubicacion")),
            observaciones=form_data.get("observaciones") or None,
        )

        expense = expense_service.create_expense(project_id, data)

        # Audit log
        audit = AuditService(expense_service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.create,
            recurso="expense",
            recurso_id=str(expense.id),
            detalle={"concepto": data.concepto, "cantidad_euros": str(data.cantidad_euros)},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Return updated tab content
    expenses = expense_service.get_project_expenses(project_id)
    summary = expense_service.get_expense_summary(project_id)
    budget_lines = expense_service.get_budget_lines_with_balance(project_id)

    return templates.TemplateResponse(
        "partials/projects/expenses_tab.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "expenses": expenses,
            "summary": summary,
            "budget_lines": budget_lines,
            "estados": EstadoGasto,
            "ubicaciones": UbicacionGasto,
        },
    )


@router.put("/{project_id}/expenses/{expense_id}", response_class=HTMLResponse)
async def update_expense(
    request: Request,
    project_id: int,
    expense_id: int,
    user: User = Depends(require_permission(Permiso.gasto_crear)),
    expense_service: ExpenseService = Depends(get_expense_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Update an expense and return updated row"""
    form_data = await request.form()

    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    expense = expense_service.get_expense_by_id(expense_id)
    if not expense or expense.project_id != project_id:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")

    try:
        # Parse form data - only include fields that are present
        update_data = {}

        if form_data.get("budget_line_id"):
            update_data["budget_line_id"] = int(form_data.get("budget_line_id"))
        if form_data.get("fecha_factura"):
            update_data["fecha_factura"] = date.fromisoformat(form_data.get("fecha_factura"))
        if form_data.get("concepto"):
            update_data["concepto"] = form_data.get("concepto")
        if form_data.get("expedidor"):
            update_data["expedidor"] = form_data.get("expedidor")
        if "persona" in form_data:
            update_data["persona"] = form_data.get("persona") or None
        if form_data.get("cantidad_original"):
            update_data["cantidad_original"] = Decimal(str(form_data.get("cantidad_original")).replace(",", "."))
        if form_data.get("moneda_original"):
            update_data["moneda_original"] = form_data.get("moneda_original")
        if "tipo_cambio" in form_data:
            update_data["tipo_cambio"] = Decimal(str(form_data.get("tipo_cambio")).replace(",", ".")) if form_data.get("tipo_cambio") else None
        if form_data.get("cantidad_euros"):
            update_data["cantidad_euros"] = Decimal(str(form_data.get("cantidad_euros")).replace(",", "."))
        if form_data.get("porcentaje"):
            update_data["porcentaje"] = Decimal(str(form_data.get("porcentaje")).replace(",", "."))
        if form_data.get("financiado_por"):
            update_data["financiado_por"] = form_data.get("financiado_por")
        if form_data.get("ubicacion"):
            update_data["ubicacion"] = UbicacionGasto(form_data.get("ubicacion"))
        if "observaciones" in form_data:
            update_data["observaciones"] = form_data.get("observaciones") or None

        data = ExpenseUpdate(**update_data)
        expense_service.update_expense(expense_id, data)

        # Audit log
        audit = AuditService(expense_service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.update,
            recurso="expense",
            recurso_id=str(expense_id),
            detalle={"campos": list(update_data.keys())},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Return updated tab content
    expenses = expense_service.get_project_expenses(project_id)
    summary = expense_service.get_expense_summary(project_id)
    budget_lines = expense_service.get_budget_lines_with_balance(project_id)

    return templates.TemplateResponse(
        "partials/projects/expenses_tab.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "expenses": expenses,
            "summary": summary,
            "budget_lines": budget_lines,
            "estados": EstadoGasto,
            "ubicaciones": UbicacionGasto,
        },
    )


@router.delete("/{project_id}/expenses/{expense_id}", response_class=HTMLResponse)
def delete_expense(
    request: Request,
    project_id: int,
    expense_id: int,
    user: User = Depends(require_permission(Permiso.gasto_crear)),
    expense_service: ExpenseService = Depends(get_expense_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Delete an expense"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    if not expense_service.delete_expense(expense_id):
        raise HTTPException(status_code=404, detail="Gasto no encontrado")

    # Audit log
    audit = AuditService(expense_service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.delete,
        recurso="expense",
        recurso_id=str(expense_id),
        detalle=None,
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    # Return updated tab content
    expenses = expense_service.get_project_expenses(project_id)
    summary = expense_service.get_expense_summary(project_id)
    budget_lines = expense_service.get_budget_lines_with_balance(project_id)

    return templates.TemplateResponse(
        "partials/projects/expenses_tab.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "expenses": expenses,
            "summary": summary,
            "budget_lines": budget_lines,
            "estados": EstadoGasto,
            "ubicaciones": UbicacionGasto,
        },
    )


@router.post("/{project_id}/expenses/{expense_id}/validate", response_class=HTMLResponse)
def validate_expense(
    request: Request,
    project_id: int,
    expense_id: int,
    user: User = Depends(require_permission(Permiso.gasto_validar)),
    expense_service: ExpenseService = Depends(get_expense_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Validate an expense"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    try:
        expense_service.validate_expense(expense_id)

        # Audit log
        audit = AuditService(expense_service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.status_change,
            recurso="expense",
            recurso_id=str(expense_id),
            detalle={"estado": "validado"},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Return updated tab content
    expenses = expense_service.get_project_expenses(project_id)
    summary = expense_service.get_expense_summary(project_id)
    budget_lines = expense_service.get_budget_lines_with_balance(project_id)

    response = templates.TemplateResponse(
        "partials/projects/expenses_tab.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "expenses": expenses,
            "summary": summary,
            "budget_lines": budget_lines,
            "estados": EstadoGasto,
            "ubicaciones": UbicacionGasto,
        },
    )
    # Trigger budget tab refresh when expense validation changes budget values
    response.headers["HX-Trigger"] = "budgetUpdated"
    return response


@router.post("/{project_id}/expenses/{expense_id}/reject", response_class=HTMLResponse)
async def reject_expense(
    request: Request,
    project_id: int,
    expense_id: int,
    user: User = Depends(require_permission(Permiso.gasto_validar)),
    expense_service: ExpenseService = Depends(get_expense_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Reject an expense"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    form_data = await request.form()
    reason = form_data.get("reason")

    try:
        expense_service.reject_expense(expense_id, reason)

        # Audit log
        audit = AuditService(expense_service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.status_change,
            recurso="expense",
            recurso_id=str(expense_id),
            detalle={"estado": "rechazado", "motivo": reason},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Return updated tab content
    expenses = expense_service.get_project_expenses(project_id)
    summary = expense_service.get_expense_summary(project_id)
    budget_lines = expense_service.get_budget_lines_with_balance(project_id)

    response = templates.TemplateResponse(
        "partials/projects/expenses_tab.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "expenses": expenses,
            "summary": summary,
            "budget_lines": budget_lines,
            "estados": EstadoGasto,
            "ubicaciones": UbicacionGasto,
        },
    )
    # Trigger budget tab refresh when expense validation changes budget values
    response.headers["HX-Trigger"] = "budgetUpdated"
    return response


@router.post("/{project_id}/expenses/{expense_id}/revert", response_class=HTMLResponse)
def revert_expense(
    request: Request,
    project_id: int,
    expense_id: int,
    user: User = Depends(require_permission(Permiso.gasto_validar)),
    expense_service: ExpenseService = Depends(get_expense_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Revert an expense to draft"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    try:
        expense_service.revert_to_draft(expense_id)

        # Audit log
        audit = AuditService(expense_service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.status_change,
            recurso="expense",
            recurso_id=str(expense_id),
            detalle={"estado": "borrador"},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Return updated tab content
    expenses = expense_service.get_project_expenses(project_id)
    summary = expense_service.get_expense_summary(project_id)
    budget_lines = expense_service.get_budget_lines_with_balance(project_id)

    response = templates.TemplateResponse(
        "partials/projects/expenses_tab.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "expenses": expenses,
            "summary": summary,
            "budget_lines": budget_lines,
            "estados": EstadoGasto,
            "ubicaciones": UbicacionGasto,
        },
    )
    # Trigger budget tab refresh when expense validation changes budget values
    response.headers["HX-Trigger"] = "budgetUpdated"
    return response


@router.get("/{project_id}/expenses/{expense_id}/upload-modal", response_class=HTMLResponse)
def upload_modal(
    request: Request,
    project_id: int,
    expense_id: int,
    user: User = Depends(require_permission(Permiso.gasto_ver)),
    expense_service: ExpenseService = Depends(get_expense_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Render upload modal for expense document"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    expense = expense_service.get_expense_by_id(expense_id)
    if not expense or expense.project_id != project_id:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")

    return templates.TemplateResponse(
        "partials/projects/expense_upload_modal.html",
        {"request": request, "project": project, "expense": expense},
    )


@router.post("/{project_id}/expenses/{expense_id}/upload", response_class=HTMLResponse)
async def upload_document(
    request: Request,
    project_id: int,
    expense_id: int,
    user: User = Depends(require_permission(Permiso.gasto_justificar)),
    file: UploadFile = File(...),
    expense_service: ExpenseService = Depends(get_expense_service),
    project_service: ProjectService = Depends(get_project_service),
    document_service: DocumentService = Depends(get_document_service),
):
    """Upload a document for an expense"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    expense = expense_service.get_expense_by_id(expense_id)
    if not expense or expense.project_id != project_id:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")

    try:
        # Save document in expense
        expense_service.save_document(expense_id, file)

        # Audit log
        audit = AuditService(expense_service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.upload,
            recurso="expense_document",
            recurso_id=str(expense_id),
            detalle={"filename": file.filename},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )

        # Also create entry in project documents with category "factura"
        await file.seek(0)
        budget_line = expense.budget_line
        concepto_short = expense.concepto[:50] if len(expense.concepto) > 50 else expense.concepto
        document_data = DocumentCreate(
            categoria=CategoriaDocumento.factura,
            descripcion=f"Factura - {budget_line.name} - {concepto_short}",
        )
        document_service.create_document(project_id, file, document_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Return updated tab content
    expenses = expense_service.get_project_expenses(project_id)
    summary = expense_service.get_expense_summary(project_id)
    budget_lines = expense_service.get_budget_lines_with_balance(project_id)

    return templates.TemplateResponse(
        "partials/projects/expenses_tab.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "expenses": expenses,
            "summary": summary,
            "budget_lines": budget_lines,
            "estados": EstadoGasto,
            "ubicaciones": UbicacionGasto,
        },
    )


@router.get("/{project_id}/expenses/{expense_id}/document")
def get_expense_document(
    project_id: int,
    expense_id: int,
    user: User = Depends(require_permission(Permiso.gasto_ver)),
    expense_service: ExpenseService = Depends(get_expense_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Serve the document file for an expense"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    expense = expense_service.get_expense_by_id(expense_id)
    if not expense or expense.project_id != project_id:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")

    if not expense.documento_path:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    if not os.path.exists(expense.documento_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    # Extract filename from path
    filename = os.path.basename(expense.documento_path)

    return FileResponse(expense.documento_path, filename=filename)
