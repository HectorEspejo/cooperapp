from datetime import datetime
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog, ActorType, AccionAuditoria


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        actor_type: ActorType,
        actor_id: str,
        actor_email: str | None,
        actor_label: str,
        accion: AccionAuditoria,
        recurso: str | None = None,
        recurso_id: str | None = None,
        detalle: dict | None = None,
        ip_address: str | None = None,
        project_id: int | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_label=actor_label,
            accion=accion,
            recurso=recurso,
            recurso_id=str(recurso_id) if recurso_id else None,
            detalle=detalle,
            ip_address=ip_address,
            project_id=project_id,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def get_logs(
        self,
        accion: AccionAuditoria | None = None,
        actor_id: str | None = None,
        project_id: int | None = None,
        fecha_desde: datetime | None = None,
        fecha_hasta: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AuditLog], int]:
        query = self.db.query(AuditLog)

        if accion:
            query = query.filter(AuditLog.accion == accion)
        if actor_id:
            query = query.filter(AuditLog.actor_id == actor_id)
        if project_id:
            query = query.filter(AuditLog.project_id == project_id)
        if fecha_desde:
            query = query.filter(AuditLog.timestamp >= fecha_desde)
        if fecha_hasta:
            query = query.filter(AuditLog.timestamp <= fecha_hasta)

        total = query.count()
        logs = query.order_by(AuditLog.timestamp.desc()).offset((page - 1) * page_size).limit(page_size).all()

        return logs, total
