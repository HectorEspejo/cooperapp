from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict, computed_field
from app.models.expense import UbicacionGasto, EstadoGasto


class ExpenseBase(BaseModel):
    """Base schema with common expense fields"""
    fecha_factura: date
    concepto: str = Field(..., max_length=500)
    expedidor: str = Field(..., max_length=200)
    persona: str | None = Field(None, max_length=200)
    cantidad_original: Decimal = Field(..., ge=0)
    moneda_original: str = Field(default="EUR", max_length=3)
    tipo_cambio: Decimal | None = Field(None, ge=0)
    cantidad_euros: Decimal = Field(..., ge=0)
    porcentaje: Decimal = Field(default=Decimal("100"), ge=0, le=100)
    financiado_por: str = Field(..., max_length=100)
    ubicacion: UbicacionGasto
    observaciones: str | None = None


class ExpenseCreate(ExpenseBase):
    """Schema for creating a new expense"""
    budget_line_id: int


class ExpenseUpdate(BaseModel):
    """Schema for updating an expense - all fields optional"""
    budget_line_id: int | None = None
    fecha_factura: date | None = None
    concepto: str | None = Field(None, max_length=500)
    expedidor: str | None = Field(None, max_length=200)
    persona: str | None = Field(None, max_length=200)
    cantidad_original: Decimal | None = Field(None, ge=0)
    moneda_original: str | None = Field(None, max_length=3)
    tipo_cambio: Decimal | None = Field(None, ge=0)
    cantidad_euros: Decimal | None = Field(None, ge=0)
    porcentaje: Decimal | None = Field(None, ge=0, le=100)
    financiado_por: str | None = Field(None, max_length=100)
    ubicacion: UbicacionGasto | None = None
    observaciones: str | None = None
    comprobacion: str | None = Field(None, max_length=100)


class BudgetLineInfo(BaseModel):
    """Brief budget line info for expense responses"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class ExpenseResponse(BaseModel):
    """Schema for expense responses"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    budget_line_id: int
    fecha_factura: date
    concepto: str
    expedidor: str
    persona: str | None
    cantidad_original: Decimal
    moneda_original: str
    tipo_cambio: Decimal | None
    cantidad_euros: Decimal
    porcentaje: Decimal
    financiado_por: str
    ubicacion: UbicacionGasto
    estado: EstadoGasto
    comprobacion: str | None
    fecha_revision: datetime | None
    observaciones: str | None
    documento_path: str | None
    created_at: datetime
    updated_at: datetime

    # Computed field
    cantidad_imputable: Decimal

    # Optional nested info
    budget_line: BudgetLineInfo | None = None


class ExpenseSummary(BaseModel):
    """Summary statistics for expenses"""
    total_registrados: int = 0
    total_borradores: int = 0
    total_pendientes: int = 0
    total_validados: int = 0
    total_rechazados: int = 0
    total_justificados: int = 0

    importe_total: Decimal = Decimal("0")
    importe_validado: Decimal = Decimal("0")
    importe_espana: Decimal = Decimal("0")
    importe_terreno: Decimal = Decimal("0")


class BudgetLineBalance(BaseModel):
    """Budget line with available balance information"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    aprobado: Decimal
    ejecutado_espana: Decimal
    ejecutado_terreno: Decimal
    disponible_espana: Decimal
    disponible_terreno: Decimal
    is_spain_only: bool


class ExpenseFilters(BaseModel):
    """Query filters for expenses"""
    budget_line_id: int | None = None
    estado: EstadoGasto | None = None
    ubicacion: UbicacionGasto | None = None
    fecha_desde: date | None = None
    fecha_hasta: date | None = None
