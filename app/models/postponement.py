from enum import Enum
from datetime import date, datetime
from sqlalchemy import String, Date, DateTime, Text, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class EstadoAplazamiento(str, Enum):
    pendiente = "pendiente"
    aprobado = "aprobado"
    rechazado = "rechazado"


class Aplazamiento(Base):
    __tablename__ = "aplazamientos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    numero_secuencial: Mapped[int] = mapped_column(Integer)

    fecha_finalizacion_anterior: Mapped[date] = mapped_column(Date)
    fecha_justificacion_anterior: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_finalizacion_nueva: Mapped[date] = mapped_column(Date)
    fecha_justificacion_nueva: Mapped[date | None] = mapped_column(Date, nullable=True)

    estado: Mapped[EstadoAplazamiento] = mapped_column(
        SQLEnum(EstadoAplazamiento), default=EstadoAplazamiento.pendiente
    )
    motivo: Mapped[str] = mapped_column(Text)
    motivo_rechazo: Mapped[str | None] = mapped_column(Text, nullable=True)

    solicitante_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    aprobador_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="aplazamientos")
    solicitante: Mapped["User"] = relationship(foreign_keys=[solicitante_id])
    aprobador: Mapped["User | None"] = relationship(foreign_keys=[aprobador_id])

    def __repr__(self) -> str:
        return f"<Aplazamiento #{self.numero_secuencial} project={self.project_id} estado={self.estado.value}>"


from app.models.project import Project
from app.models.user import User
