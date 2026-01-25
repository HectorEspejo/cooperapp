from enum import Enum
from datetime import datetime
from sqlalchemy import String, DateTime, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class TipoInforme(str, Enum):
    cuenta_justificativa = "cuenta_justificativa"
    ejecucion_presupuestaria = "ejecucion_presupuestaria"
    relacion_transferencias = "relacion_transferencias"
    ficha_proyecto = "ficha_proyecto"
    informe_tecnico_mensual = "informe_tecnico_mensual"
    informe_economico = "informe_economico"


# Spanish display names for report types
TIPO_INFORME_NOMBRES = {
    TipoInforme.cuenta_justificativa: "Cuenta Justificativa",
    TipoInforme.ejecucion_presupuestaria: "Ejecucion Presupuestaria",
    TipoInforme.relacion_transferencias: "Relacion de Transferencias",
    TipoInforme.ficha_proyecto: "Ficha del Proyecto",
    TipoInforme.informe_tecnico_mensual: "Informe Tecnico Mensual",
    TipoInforme.informe_economico: "Informe Economico",
}


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))

    tipo: Mapped[TipoInforme] = mapped_column(SQLEnum(TipoInforme), index=True)
    periodo: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g., "2024-01", "Q1-2024"
    formato_financiador: Mapped[str] = mapped_column(String(50))  # AACID, AECID, etc.

    nombre_archivo: Mapped[str] = mapped_column(String(255))
    ruta: Mapped[str] = mapped_column(String(500))
    generado_por: Mapped[str | None] = mapped_column(String(200), nullable=True)

    notas: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    project: Mapped["Project"] = relationship(back_populates="reports")

    @property
    def tipo_nombre(self) -> str:
        """Get the Spanish display name for this report type"""
        return TIPO_INFORME_NOMBRES.get(self.tipo, self.tipo.value)

    def __repr__(self) -> str:
        return f"<Report {self.id}: {self.tipo.value} - {self.nombre_archivo}>"


# Import at end to avoid circular import
from app.models.project import Project
