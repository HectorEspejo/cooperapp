from enum import Enum
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, Text, Numeric, Date, DateTime, Enum as SQLEnum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class EstadoActividad(str, Enum):
    pendiente = "pendiente"
    en_curso = "en_curso"
    completada = "completada"
    cancelada = "cancelada"


class LogicalFramework(Base):
    """Main Logical Framework entity - one per project"""
    __tablename__ = "logical_frameworks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True,
        index=True
    )
    objetivo_general: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="logical_framework")
    specific_objectives: Mapped[list["SpecificObjective"]] = relationship(
        back_populates="framework",
        cascade="all, delete-orphan",
        order_by="SpecificObjective.numero"
    )
    indicators: Mapped[list["Indicator"]] = relationship(
        back_populates="framework",
        cascade="all, delete-orphan",
        foreign_keys="Indicator.framework_id"
    )

    def __repr__(self) -> str:
        return f"<LogicalFramework project_id={self.project_id}>"


class SpecificObjective(Base):
    """Specific objectives under the general objective"""
    __tablename__ = "specific_objectives"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    framework_id: Mapped[int] = mapped_column(
        ForeignKey("logical_frameworks.id", ondelete="CASCADE"),
        index=True
    )
    numero: Mapped[int] = mapped_column(Integer)
    descripcion: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    framework: Mapped["LogicalFramework"] = relationship(back_populates="specific_objectives")
    results: Mapped[list["Result"]] = relationship(
        back_populates="objective",
        cascade="all, delete-orphan",
        order_by="Result.numero"
    )
    indicators: Mapped[list["Indicator"]] = relationship(
        back_populates="objective",
        cascade="all, delete-orphan",
        foreign_keys="Indicator.objective_id"
    )

    def __repr__(self) -> str:
        return f"<SpecificObjective OE{self.numero}>"


class Result(Base):
    """Results under specific objectives"""
    __tablename__ = "results"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    objective_id: Mapped[int] = mapped_column(
        ForeignKey("specific_objectives.id", ondelete="CASCADE"),
        index=True
    )
    numero: Mapped[str] = mapped_column(String(20))  # e.g., "R1", "R2"
    descripcion: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    objective: Mapped["SpecificObjective"] = relationship(back_populates="results")
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="result",
        cascade="all, delete-orphan",
        order_by="Activity.numero"
    )
    indicators: Mapped[list["Indicator"]] = relationship(
        back_populates="result",
        cascade="all, delete-orphan",
        foreign_keys="Indicator.result_id"
    )

    def __repr__(self) -> str:
        return f"<Result {self.numero}>"


class Activity(Base):
    """Activities under results"""
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    result_id: Mapped[int] = mapped_column(
        ForeignKey("results.id", ondelete="CASCADE"),
        index=True
    )
    numero: Mapped[str] = mapped_column(String(20))  # e.g., "A1.1", "A1.2"
    descripcion: Mapped[str] = mapped_column(Text)
    fecha_inicio_prevista: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_fin_prevista: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_inicio_real: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_fin_real: Mapped[date | None] = mapped_column(Date, nullable=True)
    estado: Mapped[EstadoActividad] = mapped_column(
        SQLEnum(EstadoActividad),
        default=EstadoActividad.pendiente
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    result: Mapped["Result"] = relationship(back_populates="activities")
    indicators: Mapped[list["Indicator"]] = relationship(
        back_populates="activity",
        cascade="all, delete-orphan",
        foreign_keys="Indicator.activity_id"
    )
    verification_sources: Mapped[list["VerificationSource"]] = relationship(
        back_populates="activity",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Activity {self.numero}>"


class Indicator(Base):
    """Indicators that can be attached at any level"""
    __tablename__ = "indicators"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Link to framework (always set for cascade delete)
    framework_id: Mapped[int] = mapped_column(
        ForeignKey("logical_frameworks.id", ondelete="CASCADE"),
        index=True
    )

    # Exactly one of these should be set (or none for general-level indicators)
    objective_id: Mapped[int | None] = mapped_column(
        ForeignKey("specific_objectives.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    result_id: Mapped[int | None] = mapped_column(
        ForeignKey("results.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # Indicator data
    codigo: Mapped[str] = mapped_column(String(50))  # e.g., "IOV1"
    descripcion: Mapped[str] = mapped_column(Text)
    unidad_medida: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fuente_verificacion: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Values (stored as strings to support both numeric and text values)
    valor_base: Mapped[str | None] = mapped_column(String(200), nullable=True)
    valor_meta: Mapped[str | None] = mapped_column(String(200), nullable=True)
    valor_actual: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Auto-calculated percentage (null if not numeric)
    porcentaje_cumplimiento: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    framework: Mapped["LogicalFramework"] = relationship(
        back_populates="indicators",
        foreign_keys=[framework_id]
    )
    objective: Mapped["SpecificObjective | None"] = relationship(
        back_populates="indicators",
        foreign_keys=[objective_id]
    )
    result: Mapped["Result | None"] = relationship(
        back_populates="indicators",
        foreign_keys=[result_id]
    )
    activity: Mapped["Activity | None"] = relationship(
        back_populates="indicators",
        foreign_keys=[activity_id]
    )
    updates: Mapped[list["IndicatorUpdate"]] = relationship(
        back_populates="indicator",
        cascade="all, delete-orphan",
        order_by="IndicatorUpdate.created_at.desc()"
    )
    verification_sources: Mapped[list["VerificationSource"]] = relationship(
        back_populates="indicator",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Indicator {self.codigo}>"

    @property
    def level(self) -> str:
        """Return the level this indicator is attached to"""
        if self.activity_id:
            return "activity"
        elif self.result_id:
            return "result"
        elif self.objective_id:
            return "objective"
        return "general"


class IndicatorUpdate(Base):
    """Audit trail for indicator value updates"""
    __tablename__ = "indicator_updates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    indicator_id: Mapped[int] = mapped_column(
        ForeignKey("indicators.id", ondelete="CASCADE"),
        index=True
    )

    # Previous and new values
    valor_anterior: Mapped[str | None] = mapped_column(String(200), nullable=True)
    valor_nuevo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    porcentaje_anterior: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    porcentaje_nuevo: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    # Audit fields
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    indicator: Mapped["Indicator"] = relationship(back_populates="updates")

    def __repr__(self) -> str:
        return f"<IndicatorUpdate indicator_id={self.indicator_id} at={self.created_at}>"


# Import at end to avoid circular import
from app.models.project import Project
from app.models.document import VerificationSource
