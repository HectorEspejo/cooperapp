from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from app.models.funding import TipoFuente


class FundingSourceCreate(BaseModel):
    nombre: str = Field(..., max_length=200)
    tipo: TipoFuente


class FundingSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    nombre: str
    tipo: TipoFuente
    orden: int
    total_aprobado: Decimal = Decimal("0")
    total_ejecutado: Decimal = Decimal("0")


class AllocationEntry(BaseModel):
    funding_source_id: int
    aprobado: Decimal = Field(..., ge=0)


class BudgetLineDistribution(BaseModel):
    allocations: list[AllocationEntry]


class FundingSummaryRow(BaseModel):
    source_id: int
    source_nombre: str
    source_tipo: TipoFuente
    total_aprobado: Decimal = Decimal("0")
    total_ejecutado: Decimal = Decimal("0")
    disponible: Decimal = Decimal("0")
    porcentaje: float = 0.0
