from enum import Enum
from datetime import datetime
from sqlalchemy import String, Text, Integer, Boolean, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CategoriaDocumento(str, Enum):
    factura = "factura"
    comprobante = "comprobante"
    fuente_verificacion = "fuente_verificacion"
    informe = "informe"
    contrato = "contrato"
    convenio = "convenio"
    acta = "acta"
    listado_asistencia = "listado_asistencia"
    foto = "foto"
    otro = "otro"


CATEGORIA_NOMBRES = {
    "factura": "Factura",
    "comprobante": "Comprobante",
    "fuente_verificacion": "Fuente de Verificacion",
    "informe": "Informe",
    "contrato": "Contrato",
    "convenio": "Convenio",
    "acta": "Acta",
    "listado_asistencia": "Listado de Asistencia",
    "foto": "Foto",
    "otro": "Otro",
}


class TipoFuenteVerificacion(str, Enum):
    foto = "foto"
    acta = "acta"
    listado_asistencia = "listado_asistencia"
    informe = "informe"
    certificado = "certificado"
    contrato = "contrato"
    otro = "otro"


TIPO_FUENTE_NOMBRES = {
    "foto": "Foto",
    "acta": "Acta",
    "listado_asistencia": "Listado de Asistencia",
    "informe": "Informe",
    "certificado": "Certificado",
    "contrato": "Contrato",
    "otro": "Otro",
}


class Document(Base):
    """Document attached to a project"""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True
    )

    # File metadata
    filename: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    file_size: Mapped[int] = mapped_column(Integer)  # bytes
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Document info
    categoria: Mapped[CategoriaDocumento] = mapped_column(
        SQLEnum(CategoriaDocumento),
        index=True
    )
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Sealing (for justification)
    sellado: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_sellado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="documents")
    verification_sources: Mapped[list["VerificationSource"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document {self.original_filename}>"

    @property
    def is_image(self) -> bool:
        """Check if document is an image"""
        return self.mime_type and self.mime_type.startswith("image/")

    @property
    def is_pdf(self) -> bool:
        """Check if document is a PDF"""
        return self.mime_type == "application/pdf"

    @property
    def file_size_human(self) -> str:
        """Return human-readable file size"""
        size = self.file_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class VerificationSource(Base):
    """Link between a document and an indicator/activity as verification source"""
    __tablename__ = "verification_sources"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Link to document
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True
    )

    # Link to indicator OR activity (exactly one should be set)
    indicator_id: Mapped[int | None] = mapped_column(
        ForeignKey("indicators.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # Source info
    tipo: Mapped[TipoFuenteVerificacion] = mapped_column(
        SQLEnum(TipoFuenteVerificacion)
    )
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    validado: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_validacion: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="verification_sources")
    indicator: Mapped["Indicator | None"] = relationship(back_populates="verification_sources")
    activity: Mapped["Activity | None"] = relationship(back_populates="verification_sources")

    def __repr__(self) -> str:
        target = f"indicator={self.indicator_id}" if self.indicator_id else f"activity={self.activity_id}"
        return f"<VerificationSource {target} doc={self.document_id}>"

    @property
    def target_type(self) -> str:
        """Return whether this is linked to an indicator or activity"""
        if self.indicator_id:
            return "indicator"
        return "activity"


# Import at end to avoid circular import
from app.models.project import Project
from app.models.logical_framework import Indicator, Activity
