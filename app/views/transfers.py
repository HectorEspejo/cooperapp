from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, Request, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.transfer import EstadoTransferencia, EntidadBancaria, MonedaLocal
from app.models.document import CategoriaDocumento
from app.models.user import User
from app.services.transfer_service import TransferService
from app.services.project_service import ProjectService
from app.services.document_service import DocumentService
from app.schemas.transfer import TransferCreate, TransferUpdate, ConfirmReceptionData
from app.schemas.document import DocumentCreate
from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import Permiso
from app.services.audit_service import AuditService
from app.models.audit_log import ActorType, AccionAuditoria

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_transfer_service(db: Session = Depends(get_db)) -> TransferService:
    return TransferService(db)


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    return DocumentService(db)


@router.get("/{project_id}/transfers", response_class=HTMLResponse)
def transfers_tab(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.transferencia_ver)),
    transfer_service: TransferService = Depends(get_transfer_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Render the transfers tab content."""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    transfers = transfer_service.get_project_transfers(project_id)
    summary = transfer_service.get_transfer_summary(project_id)
    default_moneda = transfer_service.get_default_moneda_local(project_id)

    return templates.TemplateResponse(
        "partials/projects/transfers_tab.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "transfers": transfers,
            "summary": summary,
            "default_moneda": default_moneda,
            "estados": EstadoTransferencia,
            "entidades": EntidadBancaria,
            "monedas": MonedaLocal,
        },
    )


@router.get("/{project_id}/transfers/table", response_class=HTMLResponse)
def transfers_table(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.transferencia_ver)),
    transfer_service: TransferService = Depends(get_transfer_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Render the transfers table."""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    transfers = transfer_service.get_project_transfers(project_id)

    return templates.TemplateResponse(
        "partials/projects/transfers_table.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "transfers": transfers,
        },
    )


@router.get("/{project_id}/transfers/new", response_class=HTMLResponse)
def new_transfer_form(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.transferencia_ver)),
    transfer_service: TransferService = Depends(get_transfer_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Render new transfer form modal."""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    summary = transfer_service.get_transfer_summary(project_id)
    default_moneda = transfer_service.get_default_moneda_local(project_id)
    transfers = transfer_service.get_project_transfers(project_id)
    next_numero = len(transfers) + 1

    return templates.TemplateResponse(
        "partials/projects/transfer_form.html",
        {
            "request": request,
            "project": project,
            "transfer": None,
            "summary": summary,
            "default_moneda": default_moneda,
            "next_numero": next_numero,
            "entidades": EntidadBancaria,
            "monedas": MonedaLocal,
            "is_edit": False,
        },
    )


@router.get("/{project_id}/transfers/{transfer_id}/edit", response_class=HTMLResponse)
def edit_transfer_form(
    request: Request,
    project_id: int,
    transfer_id: int,
    user: User = Depends(require_permission(Permiso.transferencia_ver)),
    transfer_service: TransferService = Depends(get_transfer_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Render edit transfer form modal."""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    transfer = transfer_service.get_transfer_by_id(transfer_id)
    if not transfer or transfer.project_id != project_id:
        raise HTTPException(status_code=404, detail="Transferencia no encontrada")

    summary = transfer_service.get_transfer_summary(project_id)
    # Add current transfer amount back to available
    summary.total_pendiente += transfer.importe_euros
    default_moneda = transfer_service.get_default_moneda_local(project_id)

    return templates.TemplateResponse(
        "partials/projects/transfer_form.html",
        {
            "request": request,
            "project": project,
            "transfer": transfer,
            "summary": summary,
            "default_moneda": default_moneda,
            "next_numero": transfer.numero,
            "entidades": EntidadBancaria,
            "monedas": MonedaLocal,
            "is_edit": True,
        },
    )


@router.post("/{project_id}/transfers", response_class=HTMLResponse)
async def create_transfer(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.transferencia_gestionar)),
    transfer_service: TransferService = Depends(get_transfer_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Create a new transfer and return updated tab."""
    form_data = await request.form()

    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    try:
        data = TransferCreate(
            total_previstas=int(form_data.get("total_previstas", 1)),
            fecha_peticion=date.fromisoformat(form_data.get("fecha_peticion")) if form_data.get("fecha_peticion") else None,
            fecha_emision=date.fromisoformat(form_data.get("fecha_emision")) if form_data.get("fecha_emision") else None,
            importe_euros=Decimal(str(form_data.get("importe_euros", "0")).replace(",", ".")),
            gastos_transferencia=Decimal(str(form_data.get("gastos_transferencia", "0")).replace(",", ".")) if form_data.get("gastos_transferencia") else Decimal("0"),
            usa_moneda_intermedia=form_data.get("usa_moneda_intermedia") == "on",
            moneda_intermedia=form_data.get("moneda_intermedia") or None,
            importe_moneda_intermedia=Decimal(str(form_data.get("importe_moneda_intermedia")).replace(",", ".")) if form_data.get("importe_moneda_intermedia") else None,
            tipo_cambio_intermedio=Decimal(str(form_data.get("tipo_cambio_intermedio")).replace(",", ".")) if form_data.get("tipo_cambio_intermedio") else None,
            moneda_local=form_data.get("moneda_local") or None,
            importe_moneda_local=Decimal(str(form_data.get("importe_moneda_local")).replace(",", ".")) if form_data.get("importe_moneda_local") else None,
            tipo_cambio_local=Decimal(str(form_data.get("tipo_cambio_local")).replace(",", ".")) if form_data.get("tipo_cambio_local") else None,
            cuenta_origen=form_data.get("cuenta_origen") or None,
            cuenta_destino=form_data.get("cuenta_destino") or None,
            entidad_bancaria=EntidadBancaria(form_data.get("entidad_bancaria")) if form_data.get("entidad_bancaria") else None,
            es_ultima=form_data.get("es_ultima") == "on",
            observaciones=form_data.get("observaciones") or None,
        )

        transfer = transfer_service.create_transfer(project_id, data)

        # Audit log
        audit = AuditService(transfer_service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.create,
            recurso="transfer",
            recurso_id=str(transfer.id),
            detalle={"importe_euros": str(data.importe_euros)},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Return updated tab content
    transfers = transfer_service.get_project_transfers(project_id)
    summary = transfer_service.get_transfer_summary(project_id)
    default_moneda = transfer_service.get_default_moneda_local(project_id)

    return templates.TemplateResponse(
        "partials/projects/transfers_tab.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "transfers": transfers,
            "summary": summary,
            "default_moneda": default_moneda,
            "estados": EstadoTransferencia,
            "entidades": EntidadBancaria,
            "monedas": MonedaLocal,
        },
    )


@router.put("/{project_id}/transfers/{transfer_id}", response_class=HTMLResponse)
async def update_transfer(
    request: Request,
    project_id: int,
    transfer_id: int,
    user: User = Depends(require_permission(Permiso.transferencia_gestionar)),
    transfer_service: TransferService = Depends(get_transfer_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Update a transfer and return updated tab."""
    form_data = await request.form()

    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    transfer = transfer_service.get_transfer_by_id(transfer_id)
    if not transfer or transfer.project_id != project_id:
        raise HTTPException(status_code=404, detail="Transferencia no encontrada")

    try:
        update_data = {}

        if form_data.get("total_previstas"):
            update_data["total_previstas"] = int(form_data.get("total_previstas"))
        if "fecha_peticion" in form_data:
            update_data["fecha_peticion"] = date.fromisoformat(form_data.get("fecha_peticion")) if form_data.get("fecha_peticion") else None
        if "fecha_emision" in form_data:
            update_data["fecha_emision"] = date.fromisoformat(form_data.get("fecha_emision")) if form_data.get("fecha_emision") else None
        if form_data.get("importe_euros"):
            update_data["importe_euros"] = Decimal(str(form_data.get("importe_euros")).replace(",", "."))
        if "gastos_transferencia" in form_data:
            update_data["gastos_transferencia"] = Decimal(str(form_data.get("gastos_transferencia")).replace(",", ".")) if form_data.get("gastos_transferencia") else Decimal("0")

        # Intermediate currency
        update_data["usa_moneda_intermedia"] = form_data.get("usa_moneda_intermedia") == "on"
        if "moneda_intermedia" in form_data:
            update_data["moneda_intermedia"] = form_data.get("moneda_intermedia") or None
        if "importe_moneda_intermedia" in form_data:
            update_data["importe_moneda_intermedia"] = Decimal(str(form_data.get("importe_moneda_intermedia")).replace(",", ".")) if form_data.get("importe_moneda_intermedia") else None
        if "tipo_cambio_intermedio" in form_data:
            update_data["tipo_cambio_intermedio"] = Decimal(str(form_data.get("tipo_cambio_intermedio")).replace(",", ".")) if form_data.get("tipo_cambio_intermedio") else None

        # Local currency
        if "moneda_local" in form_data:
            update_data["moneda_local"] = form_data.get("moneda_local") or None
        if "importe_moneda_local" in form_data:
            update_data["importe_moneda_local"] = Decimal(str(form_data.get("importe_moneda_local")).replace(",", ".")) if form_data.get("importe_moneda_local") else None
        if "tipo_cambio_local" in form_data:
            update_data["tipo_cambio_local"] = Decimal(str(form_data.get("tipo_cambio_local")).replace(",", ".")) if form_data.get("tipo_cambio_local") else None

        # Bank info
        if "cuenta_origen" in form_data:
            update_data["cuenta_origen"] = form_data.get("cuenta_origen") or None
        if "cuenta_destino" in form_data:
            update_data["cuenta_destino"] = form_data.get("cuenta_destino") or None
        if "entidad_bancaria" in form_data:
            update_data["entidad_bancaria"] = EntidadBancaria(form_data.get("entidad_bancaria")) if form_data.get("entidad_bancaria") else None

        update_data["es_ultima"] = form_data.get("es_ultima") == "on"
        if "observaciones" in form_data:
            update_data["observaciones"] = form_data.get("observaciones") or None

        data = TransferUpdate(**update_data)
        transfer_service.update_transfer(transfer_id, data)

        # Audit log
        audit = AuditService(transfer_service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.update,
            recurso="transfer",
            recurso_id=str(transfer_id),
            detalle={"campos": list(update_data.keys())},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Return updated tab content
    transfers = transfer_service.get_project_transfers(project_id)
    summary = transfer_service.get_transfer_summary(project_id)
    default_moneda = transfer_service.get_default_moneda_local(project_id)

    return templates.TemplateResponse(
        "partials/projects/transfers_tab.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "transfers": transfers,
            "summary": summary,
            "default_moneda": default_moneda,
            "estados": EstadoTransferencia,
            "entidades": EntidadBancaria,
            "monedas": MonedaLocal,
        },
    )


@router.delete("/{project_id}/transfers/{transfer_id}", response_class=HTMLResponse)
def delete_transfer(
    request: Request,
    project_id: int,
    transfer_id: int,
    user: User = Depends(require_permission(Permiso.transferencia_gestionar)),
    transfer_service: TransferService = Depends(get_transfer_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Delete a transfer."""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    try:
        if not transfer_service.delete_transfer(transfer_id):
            raise HTTPException(status_code=404, detail="Transferencia no encontrada")

        # Audit log
        audit = AuditService(transfer_service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.delete,
            recurso="transfer",
            recurso_id=str(transfer_id),
            detalle=None,
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Return updated tab content
    transfers = transfer_service.get_project_transfers(project_id)
    summary = transfer_service.get_transfer_summary(project_id)
    default_moneda = transfer_service.get_default_moneda_local(project_id)

    return templates.TemplateResponse(
        "partials/projects/transfers_tab.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "transfers": transfers,
            "summary": summary,
            "default_moneda": default_moneda,
            "estados": EstadoTransferencia,
            "entidades": EntidadBancaria,
            "monedas": MonedaLocal,
        },
    )


# State transition endpoints

@router.post("/{project_id}/transfers/{transfer_id}/approve", response_class=HTMLResponse)
def approve_transfer(
    request: Request,
    project_id: int,
    transfer_id: int,
    user: User = Depends(require_permission(Permiso.transferencia_gestionar)),
    transfer_service: TransferService = Depends(get_transfer_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Approve a transfer."""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    try:
        transfer_service.approve_transfer(transfer_id)

        # Audit log
        audit = AuditService(transfer_service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.status_change,
            recurso="transfer",
            recurso_id=str(transfer_id),
            detalle={"estado": "aprobada"},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _render_transfers_tab(request, project, transfer_service, user)


@router.post("/{project_id}/transfers/{transfer_id}/confirm-emission", response_class=HTMLResponse)
async def confirm_emission(
    request: Request,
    project_id: int,
    transfer_id: int,
    user: User = Depends(require_permission(Permiso.transferencia_gestionar)),
    transfer_service: TransferService = Depends(get_transfer_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Confirm transfer emission."""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    form_data = await request.form()
    fecha_emision = date.fromisoformat(form_data.get("fecha_emision")) if form_data.get("fecha_emision") else None

    try:
        transfer_service.confirm_emission(transfer_id, fecha_emision)

        # Audit log
        audit = AuditService(transfer_service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.status_change,
            recurso="transfer",
            recurso_id=str(transfer_id),
            detalle={"estado": "emitida"},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _render_transfers_tab(request, project, transfer_service, user)


@router.post("/{project_id}/transfers/{transfer_id}/confirm-reception", response_class=HTMLResponse)
async def confirm_reception(
    request: Request,
    project_id: int,
    transfer_id: int,
    user: User = Depends(require_permission(Permiso.transferencia_gestionar)),
    transfer_service: TransferService = Depends(get_transfer_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Confirm transfer reception."""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    form_data = await request.form()

    data = ConfirmReceptionData(
        fecha_recepcion=date.fromisoformat(form_data.get("fecha_recepcion")) if form_data.get("fecha_recepcion") else None,
        importe_moneda_local=Decimal(str(form_data.get("importe_moneda_local")).replace(",", ".")) if form_data.get("importe_moneda_local") else None,
        tipo_cambio_local=Decimal(str(form_data.get("tipo_cambio_local")).replace(",", ".")) if form_data.get("tipo_cambio_local") else None,
    )

    try:
        transfer_service.confirm_reception(transfer_id, data)

        # Audit log
        audit = AuditService(transfer_service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.status_change,
            recurso="transfer",
            recurso_id=str(transfer_id),
            detalle={"estado": "recibida"},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _render_transfers_tab(request, project, transfer_service, user)


@router.post("/{project_id}/transfers/{transfer_id}/close", response_class=HTMLResponse)
def close_transfer(
    request: Request,
    project_id: int,
    transfer_id: int,
    user: User = Depends(require_permission(Permiso.transferencia_gestionar)),
    transfer_service: TransferService = Depends(get_transfer_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Close a transfer."""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    try:
        transfer_service.close_transfer(transfer_id)

        # Audit log
        audit = AuditService(transfer_service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.status_change,
            recurso="transfer",
            recurso_id=str(transfer_id),
            detalle={"estado": "cerrada"},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _render_transfers_tab(request, project, transfer_service, user)


@router.post("/{project_id}/transfers/{transfer_id}/revert", response_class=HTMLResponse)
def revert_transfer(
    request: Request,
    project_id: int,
    transfer_id: int,
    user: User = Depends(require_permission(Permiso.transferencia_gestionar)),
    transfer_service: TransferService = Depends(get_transfer_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Revert a transfer to previous state."""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    try:
        transfer_service.revert_to_previous_state(transfer_id)

        # Audit log
        audit = AuditService(transfer_service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.status_change,
            recurso="transfer",
            recurso_id=str(transfer_id),
            detalle={"accion": "revertir"},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _render_transfers_tab(request, project, transfer_service, user)


def _render_transfers_tab(request: Request, project, transfer_service: TransferService, user: User):
    """Helper to render the transfers tab."""
    transfers = transfer_service.get_project_transfers(project.id)
    summary = transfer_service.get_transfer_summary(project.id)
    default_moneda = transfer_service.get_default_moneda_local(project.id)

    return templates.TemplateResponse(
        "partials/projects/transfers_tab.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "transfers": transfers,
            "summary": summary,
            "default_moneda": default_moneda,
            "estados": EstadoTransferencia,
            "entidades": EntidadBancaria,
            "monedas": MonedaLocal,
        },
    )


# Document upload endpoints

@router.get("/{project_id}/transfers/{transfer_id}/upload-modal", response_class=HTMLResponse)
def upload_modal(
    request: Request,
    project_id: int,
    transfer_id: int,
    user: User = Depends(require_permission(Permiso.transferencia_ver)),
    doc_type: str = Query(...),
    transfer_service: TransferService = Depends(get_transfer_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Render the document upload modal."""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    transfer = transfer_service.get_transfer_by_id(transfer_id)
    if not transfer or transfer.project_id != project_id:
        raise HTTPException(status_code=404, detail="Transferencia no encontrada")

    return templates.TemplateResponse(
        "partials/projects/transfer_upload_modal.html",
        {
            "request": request,
            "project": project,
            "transfer": transfer,
            "doc_type": doc_type,
        },
    )


@router.post("/{project_id}/transfers/{transfer_id}/upload-emision", response_class=HTMLResponse)
async def upload_emission_document(
    request: Request,
    project_id: int,
    transfer_id: int,
    user: User = Depends(require_permission(Permiso.transferencia_gestionar)),
    file: UploadFile = File(...),
    transfer_service: TransferService = Depends(get_transfer_service),
    project_service: ProjectService = Depends(get_project_service),
    document_service: DocumentService = Depends(get_document_service),
):
    """Upload emission document for a transfer."""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    transfer = transfer_service.get_transfer_by_id(transfer_id)
    if not transfer or transfer.project_id != project_id:
        raise HTTPException(status_code=404, detail="Transferencia no encontrada")

    # Get checkbox value from form
    form_data = await request.form()
    copy_to_project = form_data.get("copy_to_project") == "true"

    try:
        transfer_service.save_emission_document(transfer_id, file)

        # Audit log
        audit = AuditService(transfer_service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.upload,
            recurso="transfer_emission_doc",
            recurso_id=str(transfer_id),
            detalle={"filename": file.filename},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )

        # If checkbox marked, also create document in project documents
        if copy_to_project:
            await file.seek(0)
            document_data = DocumentCreate(
                categoria=CategoriaDocumento.factura,
                descripcion=f"Justificante emision - Transferencia {transfer.numero_display}"
            )
            document_service.create_document(project_id, file, document_data)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _render_transfers_tab(request, project, transfer_service, user)


@router.post("/{project_id}/transfers/{transfer_id}/upload-recepcion", response_class=HTMLResponse)
async def upload_reception_document(
    request: Request,
    project_id: int,
    transfer_id: int,
    user: User = Depends(require_permission(Permiso.transferencia_gestionar)),
    file: UploadFile = File(...),
    transfer_service: TransferService = Depends(get_transfer_service),
    project_service: ProjectService = Depends(get_project_service),
    document_service: DocumentService = Depends(get_document_service),
):
    """Upload reception document for a transfer."""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    transfer = transfer_service.get_transfer_by_id(transfer_id)
    if not transfer or transfer.project_id != project_id:
        raise HTTPException(status_code=404, detail="Transferencia no encontrada")

    # Get checkbox value from form
    form_data = await request.form()
    copy_to_project = form_data.get("copy_to_project") == "true"

    try:
        transfer_service.save_reception_document(transfer_id, file)

        # Audit log
        audit = AuditService(transfer_service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.upload,
            recurso="transfer_reception_doc",
            recurso_id=str(transfer_id),
            detalle={"filename": file.filename},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )

        # If checkbox marked, also create document in project documents
        if copy_to_project:
            await file.seek(0)
            document_data = DocumentCreate(
                categoria=CategoriaDocumento.factura,
                descripcion=f"Justificante recepcion - Transferencia {transfer.numero_display}"
            )
            document_service.create_document(project_id, file, document_data)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _render_transfers_tab(request, project, transfer_service, user)


@router.delete("/{project_id}/transfers/{transfer_id}/document-emision", response_class=HTMLResponse)
def delete_emission_document(
    request: Request,
    project_id: int,
    transfer_id: int,
    user: User = Depends(require_permission(Permiso.transferencia_gestionar)),
    transfer_service: TransferService = Depends(get_transfer_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Delete emission document from a transfer."""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    transfer = transfer_service.get_transfer_by_id(transfer_id)
    if not transfer or transfer.project_id != project_id:
        raise HTTPException(status_code=404, detail="Transferencia no encontrada")

    transfer_service.delete_emission_document(transfer_id)

    # Audit log
    audit = AuditService(transfer_service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.delete,
        recurso="transfer_emission_doc",
        recurso_id=str(transfer_id),
        detalle=None,
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    return _render_transfers_tab(request, project, transfer_service, user)


@router.delete("/{project_id}/transfers/{transfer_id}/document-recepcion", response_class=HTMLResponse)
def delete_reception_document(
    request: Request,
    project_id: int,
    transfer_id: int,
    user: User = Depends(require_permission(Permiso.transferencia_gestionar)),
    transfer_service: TransferService = Depends(get_transfer_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Delete reception document from a transfer."""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    transfer = transfer_service.get_transfer_by_id(transfer_id)
    if not transfer or transfer.project_id != project_id:
        raise HTTPException(status_code=404, detail="Transferencia no encontrada")

    transfer_service.delete_reception_document(transfer_id)

    # Audit log
    audit = AuditService(transfer_service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.delete,
        recurso="transfer_reception_doc",
        recurso_id=str(transfer_id),
        detalle=None,
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    return _render_transfers_tab(request, project, transfer_service, user)


@router.get("/{project_id}/transfers/{transfer_id}/document/{doc_type}")
def download_document(
    request: Request,
    project_id: int,
    transfer_id: int,
    doc_type: str,
    user: User = Depends(require_permission(Permiso.transferencia_ver)),
    transfer_service: TransferService = Depends(get_transfer_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Download a transfer document."""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    transfer = transfer_service.get_transfer_by_id(transfer_id)
    if not transfer or transfer.project_id != project_id:
        raise HTTPException(status_code=404, detail="Transferencia no encontrada")

    # Audit log
    audit = AuditService(transfer_service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.download,
        recurso=f"transfer_{doc_type}_doc",
        recurso_id=str(transfer_id),
        detalle={"tipo": doc_type},
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    if doc_type == "emision":
        if not transfer.documento_emision_path:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        return FileResponse(
            transfer.documento_emision_path,
            filename=transfer.documento_emision_filename,
        )
    elif doc_type == "recepcion":
        if not transfer.documento_recepcion_path:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        return FileResponse(
            transfer.documento_recepcion_path,
            filename=transfer.documento_recepcion_filename,
        )
    else:
        raise HTTPException(status_code=400, detail="Tipo de documento invalido")
