from enum import Enum
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, Boolean, Date, DateTime, Enum as SQLEnum, ForeignKey, Table, Column, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class EstadoProyecto(str, Enum):
    formulacion = "formulacion"
    aprobado = "aprobado"
    ejecucion = "ejecucion"
    justificacion = "justificacion"
    cerrado = "cerrado"


class TipoProyecto(str, Enum):
    desarrollo = "desarrollo"
    accion_humanitaria = "accion_humanitaria"


class Financiador(str, Enum):
    aacid = "AACID"
    aecid = "AECID"
    diputacion_malaga = "Diputación de Málaga"
    ayuntamiento_malaga = "Ayuntamiento de Málaga"


class ODS(str, Enum):
    ods_1 = "1"
    ods_2 = "2"
    ods_3 = "3"
    ods_4 = "4"
    ods_5 = "5"
    ods_6 = "6"
    ods_7 = "7"
    ods_8 = "8"
    ods_9 = "9"
    ods_10 = "10"
    ods_11 = "11"
    ods_12 = "12"
    ods_13 = "13"
    ods_14 = "14"
    ods_15 = "15"
    ods_16 = "16"
    ods_17 = "17"


# ODS names in Spanish
ODS_NOMBRES = {
    "1": "Fin de la pobreza",
    "2": "Hambre cero",
    "3": "Salud y bienestar",
    "4": "Educación de calidad",
    "5": "Igualdad de género",
    "6": "Agua limpia y saneamiento",
    "7": "Energía asequible y no contaminante",
    "8": "Trabajo decente y crecimiento económico",
    "9": "Industria, innovación e infraestructura",
    "10": "Reducción de las desigualdades",
    "11": "Ciudades y comunidades sostenibles",
    "12": "Producción y consumo responsables",
    "13": "Acción por el clima",
    "14": "Vida submarina",
    "15": "Vida de ecosistemas terrestres",
    "16": "Paz, justicia e instituciones sólidas",
    "17": "Alianzas para lograr los objetivos",
}


# Association table for Project-ODS many-to-many relationship
project_ods = Table(
    "project_ods",
    Base.metadata,
    Column("project_id", Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
    Column("ods_id", Integer, ForeignKey("ods_objetivos.id", ondelete="CASCADE"), primary_key=True),
)


class ODSObjetivo(Base):
    __tablename__ = "ods_objetivos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    numero: Mapped[str] = mapped_column(String(2), unique=True)
    nombre: Mapped[str] = mapped_column(String(200))

    projects: Mapped[list["Project"]] = relationship(
        secondary=project_ods, back_populates="ods_objetivos"
    )

    def __repr__(self) -> str:
        return f"<ODS {self.numero}: {self.nombre}>"


class Plazo(Base):
    __tablename__ = "plazos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    titulo: Mapped[str] = mapped_column(String(200))
    fecha_limite: Mapped[date] = mapped_column(Date)
    completado: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="plazos")

    def __repr__(self) -> str:
        return f"<Plazo {self.titulo}: {self.fecha_limite}>"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    codigo_contable: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    codigo_area: Mapped[str] = mapped_column(String(100))
    titulo: Mapped[str] = mapped_column(String(500))
    pais: Mapped[str] = mapped_column(String(100), index=True)
    estado: Mapped[EstadoProyecto] = mapped_column(SQLEnum(EstadoProyecto), index=True)
    tipo: Mapped[TipoProyecto] = mapped_column(SQLEnum(TipoProyecto), index=True)
    financiador: Mapped[Financiador] = mapped_column(SQLEnum(Financiador), index=True)
    sector: Mapped[str] = mapped_column(String(200))
    subvencion: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    cuenta_bancaria: Mapped[str | None] = mapped_column(String(34), nullable=True)  # IBAN max 34 chars
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_finalizacion: Mapped[date] = mapped_column(Date)
    fecha_justificacion: Mapped[date | None] = mapped_column(Date, nullable=True)
    ampliado: Mapped[bool] = mapped_column(Boolean, default=False)
    funder_id: Mapped[int | None] = mapped_column(
        ForeignKey("funders.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    plazos: Mapped[list["Plazo"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Plazo.fecha_limite"
    )
    ods_objetivos: Mapped[list["ODSObjetivo"]] = relationship(
        secondary=project_ods, back_populates="projects"
    )
    budget_lines: Mapped[list["ProjectBudgetLine"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="ProjectBudgetLine.order"
    )
    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Expense.fecha_factura.desc()"
    )
    transfers: Mapped[list["Transfer"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Transfer.numero"
    )
    logical_framework: Mapped["LogicalFramework | None"] = relationship(
        back_populates="project", cascade="all, delete-orphan", uselist=False
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Document.created_at.desc()"
    )
    reports: Mapped[list["Report"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Report.created_at.desc()"
    )
    aplazamientos: Mapped[list["Aplazamiento"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Aplazamiento.numero_secuencial"
    )
    funding_sources: Mapped[list["FuenteFinanciacion"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="FuenteFinanciacion.orden"
    )

    def __repr__(self) -> str:
        return f"<Project {self.codigo_contable}: {self.titulo[:30]}...>"


# Import at end to avoid circular import
from app.models.budget import ProjectBudgetLine
from app.models.expense import Expense
from app.models.transfer import Transfer
from app.models.logical_framework import LogicalFramework
from app.models.document import Document
from app.models.report import Report
from app.models.postponement import Aplazamiento
from app.models.funding import FuenteFinanciacion
