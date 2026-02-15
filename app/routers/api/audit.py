from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.audit_log import AuditLog, AccionAuditoria
from app.auth.dependencies import require_permission
from app.auth.permissions import Permiso
from app.services.audit_service import AuditService

router = APIRouter()


def get_service(db: Session = Depends(get_db)) -> AuditService:
    return AuditService(db)


@router.get("/audit-log")
def list_audit_logs(
    accion: str | None = Query(None),
    actor_id: str | None = Query(None),
    project_id: int | None = Query(None),
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission(Permiso.auditoria_ver)),
    service: AuditService = Depends(get_service),
):
    from datetime import datetime

    accion_enum = AccionAuditoria(accion) if accion else None
    fecha_desde = datetime.fromisoformat(desde) if desde else None
    fecha_hasta = datetime.fromisoformat(hasta) if hasta else None

    logs, total = service.get_logs(
        accion=accion_enum,
        actor_id=actor_id,
        project_id=project_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        page=page,
        page_size=page_size,
    )

    return {
        "items": [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "actor_type": log.actor_type.value,
                "actor_id": log.actor_id,
                "actor_email": log.actor_email,
                "actor_label": log.actor_label,
                "accion": log.accion.value,
                "accion_display": log.accion_display,
                "recurso": log.recurso,
                "recurso_id": log.recurso_id,
                "detalle": log.detalle,
                "ip_address": log.ip_address,
                "project_id": log.project_id,
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
