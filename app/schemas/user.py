from pydantic import BaseModel
from datetime import datetime
from app.models.user import Rol


class UserResponse(BaseModel):
    id: str
    email: str
    nombre: str
    apellidos: str
    rol: Rol | None
    activo: bool
    ultimo_acceso: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserRoleUpdate(BaseModel):
    rol: Rol | None = None


class UserProjectAssign(BaseModel):
    project_ids: list[int]
