from enum import Enum
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy import String, Integer, Numeric, Text, Date, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class UbicacionGasto(str, Enum):
    espana = "espana"
    terreno = "terreno"


class EstadoGasto(str, Enum):
    borrador = "borrador"
    pendiente_revision = "pendiente_revision"
    validado = "validado"
    rechazado = "rechazado"
    justificado = "justificado"


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    budget_line_id: Mapped[int] = mapped_column(ForeignKey("project_budget_lines.id", ondelete="RESTRICT"))

    fecha_factura: Mapped[date] = mapped_column(Date)
    concepto: Mapped[str] = mapped_column(String(500))
    expedidor: Mapped[str] = mapped_column(String(200))
    persona: Mapped[str | None] = mapped_column(String(200), nullable=True)

    cantidad_original: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    moneda_original: Mapped[str] = mapped_column(String(3), default="EUR")
    tipo_cambio: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    cantidad_euros: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    porcentaje: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("100"))
    financiado_por: Mapped[str] = mapped_column(String(100))
    ubicacion: Mapped[UbicacionGasto] = mapped_column(SQLEnum(UbicacionGasto))
    estado: Mapped[EstadoGasto] = mapped_column(SQLEnum(EstadoGasto), default=EstadoGasto.borrador)

    comprobacion: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fecha_revision: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    documento_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    funding_source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("project_funding_sources.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="expenses")
    budget_line: Mapped["ProjectBudgetLine"] = relationship(back_populates="expenses")
    funding_source: Mapped["FuenteFinanciacion | None"] = relationship()

    @property
    def cantidad_imputable(self) -> Decimal:
        """Calculate the amount attributable to this funder based on percentage"""
        return self.cantidad_euros * self.porcentaje / Decimal("100")

    def __repr__(self) -> str:
        return f"<Expense {self.id}: {self.concepto[:30]}...>"


# Import at end to avoid circular import
from app.models.project import Project
from app.models.budget import ProjectBudgetLine
from app.models.funding import FuenteFinanciacion
