from datetime import date
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.audit_log import ActorType, AccionAuditoria
from app.schemas.postponement import AplazamientoCreate
from app.services.postponement_service import PostponementService
from app.services.audit_service import AuditService
from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import Permiso

router = APIRouter()


@router.post("/{project_id}/aplazamientos")
async def create_aplazamiento(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.aplazamiento_solicitar)),
    db: Session = Depends(get_db),
):
    form_data = await request.form()

    fecha_finalizacion_nueva = form_data.get("fecha_finalizacion_nueva")
    fecha_justificacion_nueva = form_data.get("fecha_justificacion_nueva") or None
    motivo = form_data.get("motivo", "")

    data = AplazamientoCreate(
        fecha_finalizacion_nueva=date.fromisoformat(fecha_finalizacion_nueva),
        fecha_justificacion_nueva=date.fromisoformat(fecha_justificacion_nueva) if fecha_justificacion_nueva else None,
        motivo=motivo,
    )

    service = PostponementService(db)
    try:
        aplazamiento = service.create(project_id, user.id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    audit = AuditService(db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=user.id,
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.aplazamiento_solicitar,
        recurso="aplazamiento",
        recurso_id=str(aplazamiento.id),
        detalle={
            "numero_secuencial": aplazamiento.numero_secuencial,
            "fecha_finalizacion_nueva": str(aplazamiento.fecha_finalizacion_nueva),
            "motivo": aplazamiento.motivo,
        },
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@router.post("/{project_id}/aplazamientos/{aplazamiento_id}/aprobar")
def approve_aplazamiento(
    request: Request,
    project_id: int,
    aplazamiento_id: int,
    user: User = Depends(require_permission(Permiso.aplazamiento_aprobar)),
    db: Session = Depends(get_db),
):
    service = PostponementService(db)
    try:
        aplazamiento = service.approve(aplazamiento_id, user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    audit = AuditService(db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=user.id,
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.aplazamiento_aprobar,
        recurso="aplazamiento",
        recurso_id=str(aplazamiento.id),
        detalle={
            "numero_secuencial": aplazamiento.numero_secuencial,
            "fecha_finalizacion_nueva": str(aplazamiento.fecha_finalizacion_nueva),
        },
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@router.post("/{project_id}/aplazamientos/{aplazamiento_id}/rechazar")
async def reject_aplazamiento(
    request: Request,
    project_id: int,
    aplazamiento_id: int,
    user: User = Depends(require_permission(Permiso.aplazamiento_aprobar)),
    db: Session = Depends(get_db),
):
    form_data = await request.form()
    motivo_rechazo = form_data.get("motivo_rechazo", "")

    if len(motivo_rechazo) < 10:
        raise HTTPException(status_code=400, detail="El motivo de rechazo debe tener al menos 10 caracteres")

    service = PostponementService(db)
    try:
        aplazamiento = service.reject(aplazamiento_id, user.id, motivo_rechazo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    audit = AuditService(db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=user.id,
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.aplazamiento_rechazar,
        recurso="aplazamiento",
        recurso_id=str(aplazamiento.id),
        detalle={
            "numero_secuencial": aplazamiento.numero_secuencial,
            "motivo_rechazo": motivo_rechazo,
        },
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)
