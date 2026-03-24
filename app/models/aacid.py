from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


# ── Constantes ──────────────────────────────────────────────────────────

NARRATIVE_SECTIONS = {
    "2.1.1": "Antecedentes y contexto",
    "2.1.2": "Problemas e intereses identificados",
    "2.1.3": "Apropiacion, alineamiento, complementariedad y armonizacion",
    "2.2.1": "Poblacion destinataria",
    "2.2.2": "Contraparte (experiencia y capacidad de gestion)",
    "2.2.3": "Entidad solicitante (experiencia y capacidad de gestion)",
    "2.2.4": "Otras organizaciones con participacion significativa",
    "2.2.5": "Personal voluntario",
    "2.3.3": "Metodologia de ejecucion",
    "2.3.4": "Plan de trabajo",
    "2.4.1": "Viabilidad",
    "2.4.2": "Sostenibilidad",
    "2.4.3": "Impacto esperado y elementos innovadores",
    "2.4.4": "Hipotesis y riesgos",
    "2.5.1": "Enfoque basado en derechos humanos",
    "2.5.2": "Enfoque de genero y feminista",
    "2.5.3": "Enfoque basado en derechos de infancia y adolescencia",
    "2.5.4": "Enfoque de fortalecimiento democratico y dialogo social",
    "2.5.5": "Enfoque territorial multiactor",
    "2.5.6": "Enfoque de accion por el clima",
    "2.5.7": "Enfoque de diversidad cultural",
}

MARKER_NAMES = [
    "gender",
    "environmental_sustainability",
    "cultural_diversity",
    "human_rights",
    "childhood",
]


# ── Modelos ─────────────────────────────────────────────────────────────

class ProjectNarrative(Base):
    """Textos narrativos del formulario AACID (21 secciones)"""
    __tablename__ = "project_narratives"
    __table_args__ = (
        UniqueConstraint("project_id", "section_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True
    )
    section_code: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text, default="")
    max_chars: Mapped[int] = mapped_column(Integer, default=4000)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship()

    def __repr__(self) -> str:
        return f"<ProjectNarrative project_id={self.project_id} section={self.section_code}>"


class ProjectBeneficiary(Base):
    """Poblacion destinataria (1 registro por proyecto)"""
    __tablename__ = "project_beneficiaries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True,
        index=True
    )
    women_direct: Mapped[int] = mapped_column(Integer, default=0)
    men_direct: Mapped[int] = mapped_column(Integer, default=0)
    total_direct: Mapped[int] = mapped_column(Integer, default=0)
    target_groups: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    project: Mapped["Project"] = relationship()

    def __repr__(self) -> str:
        return f"<ProjectBeneficiary project_id={self.project_id}>"


class ProjectVolunteer(Base):
    """Voluntariado (1 registro por proyecto)"""
    __tablename__ = "project_volunteers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True,
        index=True
    )
    women: Mapped[int] = mapped_column(Integer, default=0)
    men: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    project: Mapped["Project"] = relationship()

    def __repr__(self) -> str:
        return f"<ProjectVolunteer project_id={self.project_id}>"


class ProjectMarker(Base):
    """Marcadores CAD"""
    __tablename__ = "project_markers"
    __table_args__ = (
        UniqueConstraint("project_id", "marker_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True
    )
    marker_name: Mapped[str] = mapped_column(String(100))
    level: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    project: Mapped["Project"] = relationship()

    def __repr__(self) -> str:
        return f"<ProjectMarker project_id={self.project_id} marker={self.marker_name}>"


# Import at end to avoid circular import
from app.models.project import Project
