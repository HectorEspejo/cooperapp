from enum import Enum
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, Boolean, Date, DateTime, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class EstadoTransferencia(str, Enum):
    solicitada = "solicitada"
    aprobada = "aprobada"
    emitida = "emitida"
    recibida = "recibida"
    cerrada = "cerrada"


class EntidadBancaria(str, Enum):
    unicaja = "UNICAJA"
    triodos = "TRIODOS"
    caixabank = "CAIXABANK"
    santander = "SANTANDER"
    bbva = "BBVA"


class MonedaLocal(str, Enum):
    htg = "HTG"  # Haitian Gourde
    mad = "MAD"  # Moroccan Dirham
    dop = "DOP"  # Dominican Peso
    xof = "XOF"  # West African CFA Franc
    usd = "USD"  # US Dollar (intermediate currency)


# Mapping from country names to local currencies
PAIS_MONEDA_MAP = {
    "Haiti": MonedaLocal.htg,
    "Haití": MonedaLocal.htg,
    "Marruecos": MonedaLocal.mad,
    "Morocco": MonedaLocal.mad,
    "Rep. Dominicana": MonedaLocal.dop,
    "República Dominicana": MonedaLocal.dop,
    "Republica Dominicana": MonedaLocal.dop,
    "Dominican Republic": MonedaLocal.dop,
    "Senegal": MonedaLocal.xof,
    "Sénégal": MonedaLocal.xof,
}


def get_moneda_for_pais(pais: str) -> MonedaLocal | None:
    """Get the local currency for a given country name."""
    return PAIS_MONEDA_MAP.get(pais)


class Transfer(Base):
    __tablename__ = "transfers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))

    # Sequential number within project (1/3, 2/3, etc.)
    numero: Mapped[int] = mapped_column(default=1)
    total_previstas: Mapped[int] = mapped_column(default=1)

    # Dates
    fecha_peticion: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_emision: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_recepcion: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Amounts in EUR
    importe_euros: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))
    gastos_transferencia: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))

    # Intermediate currency (optional, e.g., USD)
    usa_moneda_intermedia: Mapped[bool] = mapped_column(Boolean, default=False)
    moneda_intermedia: Mapped[str | None] = mapped_column(String(3), nullable=True)
    importe_moneda_intermedia: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    tipo_cambio_intermedio: Mapped[Decimal | None] = mapped_column(Numeric(15, 6), nullable=True)

    # Local currency
    moneda_local: Mapped[str | None] = mapped_column(String(3), nullable=True)
    importe_moneda_local: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    tipo_cambio_local: Mapped[Decimal | None] = mapped_column(Numeric(15, 6), nullable=True)

    # Bank information
    cuenta_origen: Mapped[str | None] = mapped_column(String(34), nullable=True)  # IBAN
    cuenta_destino: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entidad_bancaria: Mapped[EntidadBancaria | None] = mapped_column(SQLEnum(EntidadBancaria), nullable=True)

    # Status
    estado: Mapped[EstadoTransferencia] = mapped_column(
        SQLEnum(EstadoTransferencia),
        default=EstadoTransferencia.solicitada,
        index=True
    )

    # Flags
    es_ultima: Mapped[bool] = mapped_column(Boolean, default=False)

    # Notes
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Documents by phase
    documento_emision_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    documento_emision_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    documento_recepcion_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    documento_recepcion_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationship
    project: Mapped["Project"] = relationship(back_populates="transfers")

    @property
    def numero_display(self) -> str:
        """Display format: 1/3, 2/3, etc."""
        return f"{self.numero}/{self.total_previstas}"

    @property
    def importe_neto(self) -> Decimal:
        """Net amount after transfer fees."""
        return self.importe_euros - (self.gastos_transferencia or Decimal("0"))

    def __repr__(self) -> str:
        return f"<Transfer {self.id}: {self.numero_display} - {self.importe_euros} EUR ({self.estado.value})>"


# Import at end to avoid circular import
from app.models.project import Project
