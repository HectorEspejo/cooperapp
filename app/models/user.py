from enum import Enum
from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, Boolean, DateTime, Enum as SQLEnum, ForeignKey, Table, Column, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Rol(str, Enum):
    director = "director"
    coordinador = "coordinador"
    tecnico_sede = "tecnico_sede"
    gestor_pais = "gestor_pais"


user_project = Table(
    "user_project",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("project_id", Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(100))
    apellidos: Mapped[str] = mapped_column(String(200))
    entra_oid: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    rol: Mapped[Rol | None] = mapped_column(SQLEnum(Rol), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assigned_projects = relationship("Project", secondary=user_project)

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellidos}"

    @property
    def rol_display(self) -> str:
        if not self.rol:
            return "Sin rol"
        names = {
            Rol.director: "Director/a",
            Rol.coordinador: "Coordinador/a",
            Rol.tecnico_sede: "Tecnico/a de Sede",
            Rol.gestor_pais: "Gestor/a de Pais",
        }
        return names.get(self.rol, self.rol.value)
