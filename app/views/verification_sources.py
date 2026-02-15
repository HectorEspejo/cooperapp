from fastapi import APIRouter, Depends, Request, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.document import TipoFuenteVerificacion, TIPO_FUENTE_NOMBRES
from app.models.logical_framework import Indicator, Activity
from app.models.user import User
from app.services.verification_source_service import VerificationSourceService
from app.services.document_service import DocumentService
from app.services.project_service import ProjectService
from app.schemas.document import VerificationSourceCreate
from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import Permiso
from app.services.audit_service import AuditService
from app.models.audit_log import ActorType, AccionAuditoria

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_verification_service(db: Session = Depends(get_db)) -> VerificationSourceService:
    return VerificationSourceService(db)


def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    return DocumentService(db)


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


@router.get("/indicators/{indicator_id}/verification-sources", response_class=HTMLResponse)
def indicator_sources_modal(
    request: Request,
    indicator_id: int,
    user: User = Depends(require_permission(Permiso.documento_ver)),
    verification_service: VerificationSourceService = Depends(get_verification_service),
    document_service: DocumentService = Depends(get_document_service),
    db: Session = Depends(get_db),
):
    """Render verification sources modal for an indicator"""
    indicator = db.get(Indicator, indicator_id)
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")

    # Get project_id from indicator's framework
    project_id = indicator.framework.project_id

    sources = verification_service.get_indicator_sources(indicator_id)
    summary = verification_service.get_indicator_summary(indicator_id)
    available_documents = verification_service.get_available_documents(project_id)

    return templates.TemplateResponse(
        "partials/projects/verification_sources_modal.html",
        {
            "request": request,
            "target_type": "indicator",
            "target_id": indicator_id,
            "target": indicator,
            "project_id": project_id,
            "sources": sources,
            "summary": summary,
            "available_documents": available_documents,
            "tipos": TipoFuenteVerificacion,
            "tipo_nombres": TIPO_FUENTE_NOMBRES,
        },
    )


@router.get("/activities/{activity_id}/verification-sources", response_class=HTMLResponse)
def activity_sources_modal(
    request: Request,
    activity_id: int,
    user: User = Depends(require_permission(Permiso.documento_ver)),
    verification_service: VerificationSourceService = Depends(get_verification_service),
    document_service: DocumentService = Depends(get_document_service),
    db: Session = Depends(get_db),
):
    """Render verification sources modal for an activity"""
    activity = db.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    # Get project_id from activity's result's objective's framework
    project_id = activity.result.objective.framework.project_id

    sources = verification_service.get_activity_sources(activity_id)
    summary = verification_service.get_activity_summary(activity_id)
    available_documents = verification_service.get_available_documents(project_id)

    return templates.TemplateResponse(
        "partials/projects/verification_sources_modal.html",
        {
            "request": request,
            "target_type": "activity",
            "target_id": activity_id,
            "target": activity,
            "project_id": project_id,
            "sources": sources,
            "summary": summary,
            "available_documents": available_documents,
            "tipos": TipoFuenteVerificacion,
            "tipo_nombres": TIPO_FUENTE_NOMBRES,
        },
    )


@router.post("/indicators/{indicator_id}/verification-sources", response_class=HTMLResponse)
async def add_indicator_source(
    request: Request,
    indicator_id: int,
    user: User = Depends(require_permission(Permiso.documento_sellar)),
    document_id: int = Form(...),
    tipo: TipoFuenteVerificacion = Form(...),
    descripcion: str | None = Form(None),
    verification_service: VerificationSourceService = Depends(get_verification_service),
    db: Session = Depends(get_db),
):
    """Add a verification source to an indicator"""
    indicator = db.get(Indicator, indicator_id)
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")

    project_id = indicator.framework.project_id

    try:
        data = VerificationSourceCreate(
            document_id=document_id,
            indicator_id=indicator_id,
            tipo=tipo,
            descripcion=descripcion,
        )
        verification_service.create_source(data)

        # Audit log
        audit = AuditService(db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.create,
            recurso="verification_source",
            recurso_id=None,
            detalle={"indicator_id": indicator_id, "document_id": document_id},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Return updated modal content
    sources = verification_service.get_indicator_sources(indicator_id)
    summary = verification_service.get_indicator_summary(indicator_id)
    available_documents = verification_service.get_available_documents(project_id)

    return templates.TemplateResponse(
        "partials/projects/verification_sources_modal.html",
        {
            "request": request,
            "target_type": "indicator",
            "target_id": indicator_id,
            "target": indicator,
            "project_id": project_id,
            "sources": sources,
            "summary": summary,
            "available_documents": available_documents,
            "tipos": TipoFuenteVerificacion,
            "tipo_nombres": TIPO_FUENTE_NOMBRES,
        },
    )


@router.post("/activities/{activity_id}/verification-sources", response_class=HTMLResponse)
async def add_activity_source(
    request: Request,
    activity_id: int,
    user: User = Depends(require_permission(Permiso.documento_sellar)),
    document_id: int = Form(...),
    tipo: TipoFuenteVerificacion = Form(...),
    descripcion: str | None = Form(None),
    verification_service: VerificationSourceService = Depends(get_verification_service),
    db: Session = Depends(get_db),
):
    """Add a verification source to an activity"""
    activity = db.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    project_id = activity.result.objective.framework.project_id

    try:
        data = VerificationSourceCreate(
            document_id=document_id,
            activity_id=activity_id,
            tipo=tipo,
            descripcion=descripcion,
        )
        verification_service.create_source(data)

        # Audit log
        audit = AuditService(db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.create,
            recurso="verification_source",
            recurso_id=None,
            detalle={"activity_id": activity_id, "document_id": document_id},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Return updated modal content
    sources = verification_service.get_activity_sources(activity_id)
    summary = verification_service.get_activity_summary(activity_id)
    available_documents = verification_service.get_available_documents(project_id)

    return templates.TemplateResponse(
        "partials/projects/verification_sources_modal.html",
        {
            "request": request,
            "target_type": "activity",
            "target_id": activity_id,
            "target": activity,
            "project_id": project_id,
            "sources": sources,
            "summary": summary,
            "available_documents": available_documents,
            "tipos": TipoFuenteVerificacion,
            "tipo_nombres": TIPO_FUENTE_NOMBRES,
        },
    )


@router.delete("/verification-sources/{source_id}", response_class=HTMLResponse)
def delete_source(
    request: Request,
    source_id: int,
    user: User = Depends(require_permission(Permiso.documento_sellar)),
    verification_service: VerificationSourceService = Depends(get_verification_service),
    db: Session = Depends(get_db),
):
    """Delete a verification source"""
    source = verification_service.get_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Fuente de verificacion no encontrada")

    # Store info before deletion for redirect
    target_type = source.target_type
    target_id = source.indicator_id if source.indicator_id else source.activity_id
    if target_type == "indicator":
        indicator = db.get(Indicator, target_id)
        project_id = indicator.framework.project_id
        target = indicator
    else:
        activity = db.get(Activity, target_id)
        project_id = activity.result.objective.framework.project_id
        target = activity

    verification_service.delete_source(source_id)

    # Audit log
    audit = AuditService(db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.delete,
        recurso="verification_source",
        recurso_id=str(source_id),
        detalle=None,
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    # Return updated modal content
    if target_type == "indicator":
        sources = verification_service.get_indicator_sources(target_id)
        summary = verification_service.get_indicator_summary(target_id)
    else:
        sources = verification_service.get_activity_sources(target_id)
        summary = verification_service.get_activity_summary(target_id)

    available_documents = verification_service.get_available_documents(project_id)

    return templates.TemplateResponse(
        "partials/projects/verification_sources_modal.html",
        {
            "request": request,
            "target_type": target_type,
            "target_id": target_id,
            "target": target,
            "project_id": project_id,
            "sources": sources,
            "summary": summary,
            "available_documents": available_documents,
            "tipos": TipoFuenteVerificacion,
            "tipo_nombres": TIPO_FUENTE_NOMBRES,
        },
    )


@router.post("/verification-sources/{source_id}/validate", response_class=HTMLResponse)
def validate_source(
    request: Request,
    source_id: int,
    user: User = Depends(require_permission(Permiso.documento_sellar)),
    verification_service: VerificationSourceService = Depends(get_verification_service),
    db: Session = Depends(get_db),
):
    """Validate a verification source"""
    source = verification_service.get_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Fuente de verificacion no encontrada")

    target_type = source.target_type
    target_id = source.indicator_id if source.indicator_id else source.activity_id

    try:
        verification_service.validate_source(source_id)

        # Audit log
        audit = AuditService(db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.status_change,
            recurso="verification_source",
            recurso_id=str(source_id),
            detalle={"accion": "validar"},
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if target_type == "indicator":
        indicator = db.get(Indicator, target_id)
        project_id = indicator.framework.project_id
        target = indicator
        sources = verification_service.get_indicator_sources(target_id)
        summary = verification_service.get_indicator_summary(target_id)
    else:
        activity = db.get(Activity, target_id)
        project_id = activity.result.objective.framework.project_id
        target = activity
        sources = verification_service.get_activity_sources(target_id)
        summary = verification_service.get_activity_summary(target_id)

    available_documents = verification_service.get_available_documents(project_id)

    return templates.TemplateResponse(
        "partials/projects/verification_sources_modal.html",
        {
            "request": request,
            "target_type": target_type,
            "target_id": target_id,
            "target": target,
            "project_id": project_id,
            "sources": sources,
            "summary": summary,
            "available_documents": available_documents,
            "tipos": TipoFuenteVerificacion,
            "tipo_nombres": TIPO_FUENTE_NOMBRES,
        },
    )
