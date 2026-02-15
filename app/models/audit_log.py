from enum import Enum
from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, DateTime, Integer, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ActorType(str, Enum):
    internal = "internal"
    counterpart = "counterpart"


class AccionAuditoria(str, Enum):
    login = "login"
    logout = "logout"
    login_failed = "login_failed"
    session_expired = "session_expired"
    create = "create"
    update = "update"
    delete = "delete"
    status_change = "status_change"
    upload = "upload"
    download = "download"
    export = "export"
    role_change = "role_change"
    project_assign = "project_assign"
    project_unassign = "project_unassign"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    actor_type: Mapped[ActorType] = mapped_column(SQLEnum(ActorType))
    actor_id: Mapped[str] = mapped_column(String(36))
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_label: Mapped[str] = mapped_column(String(255))
    accion: Mapped[AccionAuditoria] = mapped_column(SQLEnum(AccionAuditoria))
    recurso: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recurso_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    detalle: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    project_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("projects.id"), nullable=True)

    @property
    def accion_display(self) -> str:
        names = {
            AccionAuditoria.login: "Inicio de sesion",
            AccionAuditoria.logout: "Cierre de sesion",
            AccionAuditoria.login_failed: "Login fallido",
            AccionAuditoria.session_expired: "Sesion expirada",
            AccionAuditoria.create: "Crear",
            AccionAuditoria.update: "Actualizar",
            AccionAuditoria.delete: "Eliminar",
            AccionAuditoria.status_change: "Cambio de estado",
            AccionAuditoria.upload: "Subir archivo",
            AccionAuditoria.download: "Descargar",
            AccionAuditoria.export: "Exportar",
            AccionAuditoria.role_change: "Cambio de rol",
            AccionAuditoria.project_assign: "Asignar proyecto",
            AccionAuditoria.project_unassign: "Desasignar proyecto",
        }
        return names.get(self.accion, self.accion.value)
