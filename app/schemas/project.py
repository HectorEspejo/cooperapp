from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from app.models.project import EstadoProyecto, TipoProyecto, Financiador


# Plazo Schemas
class PlazoBase(BaseModel):
    titulo: str = Field(..., max_length=200)
    fecha_limite: date
    completado: bool = False


class PlazoCreate(PlazoBase):
    pass


class PlazoUpdate(BaseModel):
    titulo: str | None = Field(None, max_length=200)
    fecha_limite: date | None = None
    completado: bool | None = None


class PlazoResponse(PlazoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_at: datetime


# ODS Schemas
class ODSResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero: str
    nombre: str


# Project Schemas
class ProjectBase(BaseModel):
    codigo_contable: str = Field(..., max_length=50)
    codigo_area: str = Field(..., max_length=100)
    titulo: str = Field(..., max_length=500)
    pais: str = Field(..., max_length=100)
    estado: EstadoProyecto
    tipo: TipoProyecto
    financiador: Financiador
    sector: str = Field(..., max_length=200)
    subvencion: Decimal = Field(..., ge=0, decimal_places=2)
    cuenta_bancaria: str | None = Field(None, max_length=34)
    fecha_inicio: date
    fecha_finalizacion: date
    fecha_justificacion: date | None = None
    ampliado: bool = False


class ProjectCreate(ProjectBase):
    plazos: list[PlazoCreate] = []
    ods_ids: list[int] = []


class ProjectUpdate(BaseModel):
    codigo_contable: str | None = Field(None, max_length=50)
    codigo_area: str | None = Field(None, max_length=100)
    titulo: str | None = Field(None, max_length=500)
    pais: str | None = Field(None, max_length=100)
    estado: EstadoProyecto | None = None
    tipo: TipoProyecto | None = None
    financiador: Financiador | None = None
    sector: str | None = Field(None, max_length=200)
    subvencion: Decimal | None = Field(None, ge=0)
    cuenta_bancaria: str | None = Field(None, max_length=34)
    fecha_inicio: date | None = None
    fecha_finalizacion: date | None = None
    fecha_justificacion: date | None = None
    ampliado: bool | None = None
    ods_ids: list[int] | None = None


class ProjectResponse(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plazos: list[PlazoResponse] = []
    ods_objetivos: list[ODSResponse] = []
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProjectStats(BaseModel):
    total_projects: int
    total_subvencion: Decimal
    by_estado: dict[str, int]
    by_tipo: dict[str, int]
    by_pais: dict[str, int]
