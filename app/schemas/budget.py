from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from app.models.budget import CategoriaPartida


class FunderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    max_indirect_percentage: Decimal | None
    max_personnel_percentage: Decimal | None
    min_amount_for_audit: Decimal | None
    created_at: datetime


class BudgetLineTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    funder_id: int
    parent_id: int | None
    code: str
    name: str
    category: CategoriaPartida
    is_spain_only: bool
    order: int
    max_percentage: Decimal | None


class ProjectBudgetLineCreate(BaseModel):
    code: str = Field(..., max_length=20)
    name: str = Field(..., max_length=200)
    category: CategoriaPartida
    is_spain_only: bool = False
    order: int = 0
    aprobado: Decimal = Field(default=Decimal("0"), ge=0)
    ejecutado_espana: Decimal = Field(default=Decimal("0"), ge=0)
    ejecutado_terreno: Decimal = Field(default=Decimal("0"), ge=0)


class ProjectBudgetLineUpdate(BaseModel):
    aprobado: Decimal | None = Field(None, ge=0)
    ejecutado_espana: Decimal | None = Field(None, ge=0)
    ejecutado_terreno: Decimal | None = Field(None, ge=0)


class ProjectBudgetLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    template_id: int | None
    parent_id: int | None
    code: str
    name: str
    category: CategoriaPartida
    is_spain_only: bool
    order: int
    max_percentage: Decimal | None
    aprobado: Decimal
    ejecutado_espana: Decimal
    ejecutado_terreno: Decimal
    total_ejecutado: Decimal
    diferencia: Decimal
    porcentaje_ejecucion: float
    has_deviation_alert: bool
    has_max_percentage_alert: bool = False
    is_optional: bool = False  # For audit lines when below threshold
    created_at: datetime
    updated_at: datetime


class BudgetTotals(BaseModel):
    total_aprobado: Decimal
    total_ejecutado_espana: Decimal
    total_ejecutado_terreno: Decimal
    total_ejecutado: Decimal
    total_diferencia: Decimal
    porcentaje_ejecucion_global: float


class CategorySubtotal(BaseModel):
    category: CategoriaPartida
    category_name: str
    total_aprobado: Decimal
    total_ejecutado_espana: Decimal
    total_ejecutado_terreno: Decimal
    total_ejecutado: Decimal
    total_diferencia: Decimal
    porcentaje_ejecucion: float
    lines: list[ProjectBudgetLineResponse]


class BudgetValidationAlert(BaseModel):
    line_id: int | None
    line_code: str | None
    message: str
    alert_type: str  # "warning" or "error"


class BudgetSummary(BaseModel):
    project_id: int
    project_subvencion: Decimal | None = None
    funder_id: int | None
    funder_code: str | None
    funder_name: str | None
    funder_max_indirect_percentage: Decimal | None = None
    funder_max_personnel_percentage: Decimal | None = None
    funder_min_amount_for_audit: Decimal | None = None
    audit_required: bool = True  # False if subvencion < min_amount_for_audit
    lines: list[ProjectBudgetLineResponse]
    category_subtotals: list[CategorySubtotal] = []
    totals: BudgetTotals
    has_budget: bool
    validation_alerts: list[BudgetValidationAlert] = []
