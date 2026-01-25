from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from app.models.logical_framework import EstadoActividad


# ======================== Indicator Update Schemas ========================

class IndicatorUpdateBase(BaseModel):
    valor_nuevo: str | None = None
    observaciones: str | None = None
    updated_by: str | None = None


class IndicatorUpdateCreate(IndicatorUpdateBase):
    pass


class IndicatorUpdateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    indicator_id: int
    valor_anterior: str | None = None
    valor_nuevo: str | None = None
    porcentaje_anterior: Decimal | None = None
    porcentaje_nuevo: Decimal | None = None
    observaciones: str | None = None
    updated_by: str | None = None
    created_at: datetime


# ======================== Indicator Schemas ========================

class IndicatorBase(BaseModel):
    codigo: str = Field(..., max_length=50)
    descripcion: str
    unidad_medida: str | None = Field(None, max_length=100)
    fuente_verificacion: str | None = None
    valor_base: str | None = Field(None, max_length=200)
    valor_meta: str | None = Field(None, max_length=200)
    valor_actual: str | None = Field(None, max_length=200)


class IndicatorCreate(IndicatorBase):
    framework_id: int | None = None
    objective_id: int | None = None
    result_id: int | None = None
    activity_id: int | None = None


class IndicatorUpdate(BaseModel):
    codigo: str | None = Field(None, max_length=50)
    descripcion: str | None = None
    unidad_medida: str | None = Field(None, max_length=100)
    fuente_verificacion: str | None = None
    valor_base: str | None = Field(None, max_length=200)
    valor_meta: str | None = Field(None, max_length=200)


class IndicatorResponse(IndicatorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    framework_id: int
    objective_id: int | None = None
    result_id: int | None = None
    activity_id: int | None = None
    porcentaje_cumplimiento: Decimal | None = None
    created_at: datetime
    updated_at: datetime


class IndicatorDetailResponse(IndicatorResponse):
    updates: list[IndicatorUpdateResponse] = []


# ======================== Activity Schemas ========================

class ActivityBase(BaseModel):
    numero: str = Field(..., max_length=20)
    descripcion: str
    fecha_inicio_prevista: date | None = None
    fecha_fin_prevista: date | None = None
    fecha_inicio_real: date | None = None
    fecha_fin_real: date | None = None
    estado: EstadoActividad = EstadoActividad.pendiente


class ActivityCreate(ActivityBase):
    result_id: int | None = None


class ActivityUpdate(BaseModel):
    numero: str | None = Field(None, max_length=20)
    descripcion: str | None = None
    fecha_inicio_prevista: date | None = None
    fecha_fin_prevista: date | None = None
    fecha_inicio_real: date | None = None
    fecha_fin_real: date | None = None
    estado: EstadoActividad | None = None


class ActivityResponse(ActivityBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    result_id: int
    created_at: datetime
    updated_at: datetime


class ActivityDetailResponse(ActivityResponse):
    indicators: list[IndicatorResponse] = []


# ======================== Result Schemas ========================

class ResultBase(BaseModel):
    numero: str = Field(..., max_length=20)
    descripcion: str


class ResultCreate(ResultBase):
    objective_id: int | None = None


class ResultUpdate(BaseModel):
    numero: str | None = Field(None, max_length=20)
    descripcion: str | None = None


class ResultResponse(ResultBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    objective_id: int
    created_at: datetime
    updated_at: datetime


class ResultDetailResponse(ResultResponse):
    activities: list[ActivityDetailResponse] = []
    indicators: list[IndicatorResponse] = []


# ======================== Specific Objective Schemas ========================

class SpecificObjectiveBase(BaseModel):
    numero: int
    descripcion: str


class SpecificObjectiveCreate(SpecificObjectiveBase):
    framework_id: int | None = None


class SpecificObjectiveUpdate(BaseModel):
    numero: int | None = None
    descripcion: str | None = None


class SpecificObjectiveResponse(SpecificObjectiveBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    framework_id: int
    created_at: datetime
    updated_at: datetime


class SpecificObjectiveDetailResponse(SpecificObjectiveResponse):
    results: list[ResultDetailResponse] = []
    indicators: list[IndicatorResponse] = []


# ======================== Logical Framework Schemas ========================

class LogicalFrameworkBase(BaseModel):
    objetivo_general: str | None = None


class LogicalFrameworkCreate(LogicalFrameworkBase):
    project_id: int


class LogicalFrameworkUpdate(BaseModel):
    objetivo_general: str | None = None


class LogicalFrameworkResponse(LogicalFrameworkBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime


class LogicalFrameworkDetailResponse(LogicalFrameworkResponse):
    specific_objectives: list[SpecificObjectiveDetailResponse] = []
    indicators: list[IndicatorResponse] = []  # General-level indicators


# ======================== Summary Schemas ========================

class FrameworkSummary(BaseModel):
    total_objectives: int = 0
    total_results: int = 0
    total_activities: int = 0
    activities_completed: int = 0
    activities_in_progress: int = 0
    activities_pending: int = 0
    total_indicators: int = 0
    indicators_updated: int = 0
    average_completion: Decimal | None = None
