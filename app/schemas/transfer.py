from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from app.models.transfer import EstadoTransferencia, EntidadBancaria, MonedaLocal


class TransferBase(BaseModel):
    """Base schema with common transfer fields"""
    total_previstas: int = Field(default=1, ge=1, le=20)
    fecha_peticion: date | None = None
    fecha_emision: date | None = None
    importe_euros: Decimal = Field(..., ge=0)
    gastos_transferencia: Decimal = Field(default=Decimal("0"), ge=0)

    # Intermediate currency (optional)
    usa_moneda_intermedia: bool = False
    moneda_intermedia: str | None = Field(None, max_length=3)
    importe_moneda_intermedia: Decimal | None = Field(None, ge=0)
    tipo_cambio_intermedio: Decimal | None = Field(None, ge=0)

    # Local currency
    moneda_local: str | None = Field(None, max_length=3)
    importe_moneda_local: Decimal | None = Field(None, ge=0)
    tipo_cambio_local: Decimal | None = Field(None, ge=0)

    # Bank information
    cuenta_origen: str | None = Field(None, max_length=34)
    cuenta_destino: str | None = Field(None, max_length=100)
    entidad_bancaria: EntidadBancaria | None = None

    # Flags
    es_ultima: bool = False

    # Notes
    observaciones: str | None = None


class TransferCreate(TransferBase):
    """Schema for creating a new transfer"""
    pass


class TransferUpdate(BaseModel):
    """Schema for updating a transfer - all fields optional"""
    total_previstas: int | None = Field(None, ge=1, le=20)
    fecha_peticion: date | None = None
    fecha_emision: date | None = None
    fecha_recepcion: date | None = None
    importe_euros: Decimal | None = Field(None, ge=0)
    gastos_transferencia: Decimal | None = Field(None, ge=0)

    # Intermediate currency
    usa_moneda_intermedia: bool | None = None
    moneda_intermedia: str | None = Field(None, max_length=3)
    importe_moneda_intermedia: Decimal | None = Field(None, ge=0)
    tipo_cambio_intermedio: Decimal | None = Field(None, ge=0)

    # Local currency
    moneda_local: str | None = Field(None, max_length=3)
    importe_moneda_local: Decimal | None = Field(None, ge=0)
    tipo_cambio_local: Decimal | None = Field(None, ge=0)

    # Bank information
    cuenta_origen: str | None = Field(None, max_length=34)
    cuenta_destino: str | None = Field(None, max_length=100)
    entidad_bancaria: EntidadBancaria | None = None

    # Flags
    es_ultima: bool | None = None

    # Notes
    observaciones: str | None = None


class TransferResponse(BaseModel):
    """Schema for transfer responses"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    numero: int
    total_previstas: int
    numero_display: str

    # Dates
    fecha_peticion: date | None
    fecha_emision: date | None
    fecha_recepcion: date | None

    # Amounts
    importe_euros: Decimal
    gastos_transferencia: Decimal
    importe_neto: Decimal

    # Intermediate currency
    usa_moneda_intermedia: bool
    moneda_intermedia: str | None
    importe_moneda_intermedia: Decimal | None
    tipo_cambio_intermedio: Decimal | None

    # Local currency
    moneda_local: str | None
    importe_moneda_local: Decimal | None
    tipo_cambio_local: Decimal | None

    # Bank information
    cuenta_origen: str | None
    cuenta_destino: str | None
    entidad_bancaria: EntidadBancaria | None

    # Status and flags
    estado: EstadoTransferencia
    es_ultima: bool

    # Notes
    observaciones: str | None

    # Timestamps
    created_at: datetime
    updated_at: datetime


class TransferSummary(BaseModel):
    """Summary statistics for project transfers"""
    # Budget calculations
    presupuesto_total: Decimal = Decimal("0")  # subvencion
    gastos_espana_validados: Decimal = Decimal("0")  # sum of validated Spain expenses
    presupuesto_a_transferir: Decimal = Decimal("0")  # subvencion - gastos_espana

    # Transfer totals
    total_enviado: Decimal = Decimal("0")  # sum of transfers in emitida/recibida/cerrada
    total_pendiente: Decimal = Decimal("0")  # presupuesto_a_transferir - total_enviado
    porcentaje_transferido: Decimal = Decimal("0")

    # Counts
    transferencias_realizadas: int = 0
    transferencias_previstas: int = 0

    # Fees
    total_gastos_transferencia: Decimal = Decimal("0")


class ConfirmReceptionData(BaseModel):
    """Data for confirming transfer reception"""
    fecha_recepcion: date | None = None
    importe_moneda_local: Decimal | None = None
    tipo_cambio_local: Decimal | None = None
