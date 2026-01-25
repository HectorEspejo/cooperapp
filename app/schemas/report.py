from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.report import TipoInforme


class ReportBase(BaseModel):
    tipo: TipoInforme
    periodo: str | None = None


class ReportCreate(ReportBase):
    generado_por: str | None = None


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    tipo: TipoInforme
    tipo_nombre: str
    periodo: str | None
    formato_financiador: str
    nombre_archivo: str
    ruta: str
    generado_por: str | None
    notas: str | None
    created_at: datetime


class ReportListResponse(BaseModel):
    items: list[ReportResponse]
    total: int


class ReportValidationWarning(BaseModel):
    tipo: str  # "expense", "transfer", "indicator"
    mensaje: str
    count: int


class ReportValidationResult(BaseModel):
    can_generate: bool = True
    warnings: list[ReportValidationWarning] = Field(default_factory=list)


class ReportGenerateRequest(BaseModel):
    tipo: TipoInforme
    periodo: str | None = None
    generado_por: str | None = None


class PackGenerateRequest(BaseModel):
    tipos: list[TipoInforme] | None = None  # If None, generate all applicable types
    generado_por: str | None = None
