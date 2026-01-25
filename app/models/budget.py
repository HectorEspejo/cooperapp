from enum import Enum
from decimal import Decimal
from datetime import datetime
from sqlalchemy import String, Numeric, Boolean, Integer, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CategoriaPartida(str, Enum):
    servicios = "servicios"
    personal = "personal"
    gastos_directos = "gastos_directos"
    inversiones = "inversiones"
    indirectos = "indirectos"


class Funder(Base):
    __tablename__ = "funders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    max_indirect_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    max_personnel_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    min_amount_for_audit: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    templates: Mapped[list["BudgetLineTemplate"]] = relationship(
        back_populates="funder", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Funder {self.code}: {self.name}>"


class BudgetLineTemplate(Base):
    __tablename__ = "budget_line_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    funder_id: Mapped[int] = mapped_column(ForeignKey("funders.id", ondelete="CASCADE"))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("budget_line_templates.id", ondelete="CASCADE"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[CategoriaPartida] = mapped_column(SQLEnum(CategoriaPartida))
    is_spain_only: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, default=0)
    max_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    funder: Mapped["Funder"] = relationship(back_populates="templates")
    parent: Mapped["BudgetLineTemplate | None"] = relationship(
        "BudgetLineTemplate", remote_side=[id], back_populates="children"
    )
    children: Mapped[list["BudgetLineTemplate"]] = relationship(
        "BudgetLineTemplate", back_populates="parent", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<BudgetLineTemplate {self.code}: {self.name}>"


class ProjectBudgetLine(Base):
    __tablename__ = "project_budget_lines"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("budget_line_templates.id", ondelete="SET NULL"), nullable=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_budget_lines.id", ondelete="CASCADE"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[CategoriaPartida] = mapped_column(SQLEnum(CategoriaPartida))
    is_spain_only: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, default=0)
    max_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    aprobado: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))
    ejecutado_espana: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))
    ejecutado_terreno: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    project: Mapped["Project"] = relationship(back_populates="budget_lines")
    template: Mapped["BudgetLineTemplate | None"] = relationship()
    parent: Mapped["ProjectBudgetLine | None"] = relationship(
        "ProjectBudgetLine", remote_side=[id], back_populates="children"
    )
    children: Mapped[list["ProjectBudgetLine"]] = relationship(
        "ProjectBudgetLine", back_populates="parent", cascade="all, delete-orphan"
    )
    expenses: Mapped[list["Expense"]] = relationship(back_populates="budget_line")

    @property
    def disponible_espana(self) -> Decimal:
        """Calculate available budget for Spain location"""
        return self.aprobado - self.ejecutado_espana

    @property
    def disponible_terreno(self) -> Decimal:
        """Calculate available budget for field location"""
        return self.aprobado - self.ejecutado_terreno

    @property
    def total_ejecutado(self) -> Decimal:
        return self.ejecutado_espana + self.ejecutado_terreno

    @property
    def diferencia(self) -> Decimal:
        return self.aprobado - self.total_ejecutado

    @property
    def porcentaje_ejecucion(self) -> float:
        if self.aprobado == 0:
            return 0.0
        return float((self.total_ejecutado / self.aprobado) * 100)

    @property
    def has_deviation_alert(self) -> bool:
        if self.aprobado == 0:
            return False
        deviation = abs(self.porcentaje_ejecucion - 100)
        return deviation > 10

    def __repr__(self) -> str:
        return f"<ProjectBudgetLine {self.code}: {self.name}>"


# Import at end to avoid circular import
from app.models.project import Project
from app.models.expense import Expense
