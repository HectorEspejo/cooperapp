from enum import Enum
from decimal import Decimal
from datetime import datetime
from sqlalchemy import String, Numeric, Integer, DateTime, Enum as SQLEnum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class TipoFuente(str, Enum):
    agencia = "agencia"
    prodiversa = "prodiversa"
    contraparte = "contraparte"
    otro = "otro"


TIPO_FUENTE_NOMBRES = {
    TipoFuente.agencia: "Agencia financiadora",
    TipoFuente.prodiversa: "Prodiversa",
    TipoFuente.contraparte: "Contraparte local",
    TipoFuente.otro: "Otro co-financiador",
}


class FuenteFinanciacion(Base):
    __tablename__ = "project_funding_sources"
    __table_args__ = (
        UniqueConstraint("project_id", "nombre", name="uq_project_funding_source_nombre"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    nombre: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[TipoFuente] = mapped_column(SQLEnum(TipoFuente))
    orden: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="funding_sources")
    allocations: Mapped[list["AsignacionFinanciador"]] = relationship(
        back_populates="funding_source", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<FuenteFinanciacion {self.nombre} ({self.tipo.value})>"


class AsignacionFinanciador(Base):
    __tablename__ = "budget_line_funding"
    __table_args__ = (
        UniqueConstraint("budget_line_id", "funding_source_id", name="uq_budget_line_funding"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    budget_line_id: Mapped[int] = mapped_column(ForeignKey("project_budget_lines.id", ondelete="CASCADE"))
    funding_source_id: Mapped[int] = mapped_column(ForeignKey("project_funding_sources.id", ondelete="CASCADE"))
    aprobado: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))

    budget_line: Mapped["ProjectBudgetLine"] = relationship(back_populates="funding_allocations")
    funding_source: Mapped["FuenteFinanciacion"] = relationship(back_populates="allocations")

    def __repr__(self) -> str:
        return f"<AsignacionFinanciador line={self.budget_line_id} source={self.funding_source_id} aprobado={self.aprobado}>"


# Import at end to avoid circular import
from app.models.project import Project
from app.models.budget import ProjectBudgetLine
