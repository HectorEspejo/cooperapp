from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ProjectAACIDFieldsUpdate(BaseModel):
    convocatoria: str | None = Field(None, max_length=200)
    numero_aacid: str | None = Field(None, max_length=100)
    municipios: str | None = None
    duracion_meses: int | None = Field(None, ge=1)
    descripcion_breve: str | None = Field(None, max_length=1000)
    crs_sector_1: str | None = Field(None, max_length=200)
    crs_sector_2: str | None = Field(None, max_length=200)
    crs_sector_3: str | None = Field(None, max_length=200)
    ods_meta_1: str | None = Field(None, max_length=200)
    ods_meta_2: str | None = Field(None, max_length=200)
    ods_meta_3: str | None = Field(None, max_length=200)


class ProjectAACIDFieldsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    convocatoria: str | None = None
    numero_aacid: str | None = None
    municipios: str | None = None
    duracion_meses: int | None = None
    descripcion_breve: str | None = None
    crs_sector_1: str | None = None
    crs_sector_2: str | None = None
    crs_sector_3: str | None = None
    ods_meta_1: str | None = None
    ods_meta_2: str | None = None
    ods_meta_3: str | None = None


class NarrativeUpsert(BaseModel):
    content: str = Field(..., max_length=4000)


class NarrativeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    section_code: str
    content: str
    max_chars: int
    updated_at: datetime


class BeneficiaryUpdate(BaseModel):
    women_direct: int = Field(0, ge=0)
    men_direct: int = Field(0, ge=0)
    total_direct: int = Field(0, ge=0)
    target_groups: str | None = None


class BeneficiaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    women_direct: int
    men_direct: int
    total_direct: int
    target_groups: str | None


class VolunteerUpdate(BaseModel):
    women: int = Field(0, ge=0)
    men: int = Field(0, ge=0)
    total: int = Field(0, ge=0)


class VolunteerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    women: int
    men: int
    total: int


class MarkerUpdate(BaseModel):
    marker_name: str = Field(..., max_length=100)
    level: str = Field(..., pattern="^(principal|significant|none)$")


class MarkerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    marker_name: str
    level: str


class AACIDValidationError(BaseModel):
    field: str
    label: str
    message: str


class AACIDValidationWarning(BaseModel):
    field: str
    label: str
    current: int
    max: int
    excess: int


class AACIDValidationResult(BaseModel):
    valid: bool = True
    errors: list[AACIDValidationError] = Field(default_factory=list)
    warnings: list[AACIDValidationWarning] = Field(default_factory=list)


class AACIDPreviewSection(BaseModel):
    code: str
    label: str
    chars: int
    max_chars: int
    filled: bool
    exceeds: bool
    excess: int


class AACIDPreviewResponse(BaseModel):
    validation: AACIDValidationResult
    sections: list[AACIDPreviewSection]
