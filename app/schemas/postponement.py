from datetime import date
from pydantic import BaseModel, Field


class AplazamientoCreate(BaseModel):
    fecha_finalizacion_nueva: date
    fecha_justificacion_nueva: date | None = None
    motivo: str = Field(..., min_length=10)


class AplazamientoReject(BaseModel):
    motivo_rechazo: str = Field(..., min_length=10)
