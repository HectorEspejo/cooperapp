from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.models.document import CategoriaDocumento, TipoFuenteVerificacion


# Document Schemas
class DocumentBase(BaseModel):
    categoria: CategoriaDocumento
    descripcion: str | None = None


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    categoria: CategoriaDocumento | None = None
    descripcion: str | None = None


class DocumentResponse(DocumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    mime_type: str | None
    sellado: bool
    fecha_sellado: datetime | None
    created_at: datetime
    updated_at: datetime

    # Computed properties
    is_image: bool
    is_pdf: bool
    file_size_human: str


class DocumentSummary(BaseModel):
    total: int = 0
    by_categoria: dict[str, int] = {}
    sellados: int = 0
    pendientes_sellar: int = 0
    vinculados: int = 0
    huerfanos: int = 0
    tamano_total: int = 0
    tamano_total_human: str = "0 B"


class DocumentFilters(BaseModel):
    categoria: CategoriaDocumento | None = None
    sellado: bool | None = None
    vinculado: bool | None = None


# Verification Source Schemas
class VerificationSourceBase(BaseModel):
    tipo: TipoFuenteVerificacion
    descripcion: str | None = None


class VerificationSourceCreate(VerificationSourceBase):
    document_id: int
    indicator_id: int | None = None
    activity_id: int | None = None


class VerificationSourceUpdate(BaseModel):
    tipo: TipoFuenteVerificacion | None = None
    descripcion: str | None = None


class VerificationSourceResponse(VerificationSourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    indicator_id: int | None
    activity_id: int | None
    validado: bool
    fecha_validacion: datetime | None
    created_at: datetime
    updated_at: datetime

    # Include document info for display
    document: DocumentResponse | None = None


class VerificationSourceSummary(BaseModel):
    total: int = 0
    validados: int = 0
    pendientes: int = 0
    by_tipo: dict[str, int] = {}


class VerificationSourceWithDocument(VerificationSourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    indicator_id: int | None
    activity_id: int | None
    validado: bool
    fecha_validacion: datetime | None

    # Nested document info
    document_filename: str = ""
    document_original_filename: str = ""
    document_is_image: bool = False
    document_is_pdf: bool = False
