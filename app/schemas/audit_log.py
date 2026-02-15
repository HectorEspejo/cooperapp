from pydantic import BaseModel
from datetime import datetime
from app.models.audit_log import ActorType, AccionAuditoria


class AuditLogResponse(BaseModel):
    id: str
    timestamp: datetime
    actor_type: ActorType
    actor_id: str
    actor_email: str | None
    actor_label: str
    accion: AccionAuditoria
    recurso: str | None
    recurso_id: str | None
    detalle: dict | None
    ip_address: str | None
    project_id: int | None

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
