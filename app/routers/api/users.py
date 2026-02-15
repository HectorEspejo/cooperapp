from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User, Rol
from app.models.audit_log import ActorType, AccionAuditoria
from app.auth.dependencies import require_permission
from app.auth.permissions import Permiso
from app.services.user_service import UserService
from app.services.audit_service import AuditService

router = APIRouter()


def get_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


@router.get("/users")
def list_users(
    rol: str | None = None,
    activo: str | None = None,
    search: str | None = None,
    user: User = Depends(require_permission(Permiso.usuarios_gestionar)),
    service: UserService = Depends(get_service),
):
    rol_filter = Rol(rol) if rol else None
    activo_filter = activo == "true" if activo is not None else None
    return service.get_all(rol=rol_filter, activo=activo_filter, search=search)


@router.get("/users/{user_id}")
def get_user(
    user_id: str,
    user: User = Depends(require_permission(Permiso.usuarios_gestionar)),
    service: UserService = Depends(get_service),
):
    target = service.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return target


@router.put("/users/{user_id}/role")
async def change_role(
    request: Request,
    user_id: str,
    request_data: dict,
    user: User = Depends(require_permission(Permiso.usuarios_gestionar)),
    service: UserService = Depends(get_service),
    db: Session = Depends(get_db),
):
    target = service.get_by_id(user_id)
    old_rol = target.rol.value if target and target.rol else None

    rol_value = request_data.get("rol")
    rol = Rol(rol_value) if rol_value else None
    result = service.update_role(user_id, rol)
    if not result:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    audit = AuditService(db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=user.id,
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.role_change,
        recurso="user",
        recurso_id=user_id,
        detalle={"old_rol": old_rol, "new_rol": rol_value},
        ip_address=request.client.host if request.client else None,
    )

    return {"success": True, "rol": result.rol.value if result.rol else None}


@router.put("/users/{user_id}/toggle-active")
def toggle_active(
    request: Request,
    user_id: str,
    user: User = Depends(require_permission(Permiso.usuarios_gestionar)),
    service: UserService = Depends(get_service),
    db: Session = Depends(get_db),
):
    result = service.toggle_active(user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    audit = AuditService(db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=user.id,
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.update,
        recurso="user",
        recurso_id=user_id,
        detalle={"activo": result.activo},
        ip_address=request.client.host if request.client else None,
    )

    return {"success": True, "activo": result.activo}


@router.post("/users/{user_id}/projects")
async def assign_projects(
    request: Request,
    user_id: str,
    request_data: dict,
    user: User = Depends(require_permission(Permiso.usuarios_gestionar)),
    service: UserService = Depends(get_service),
    db: Session = Depends(get_db),
):
    project_ids = request_data.get("project_ids", [])
    audit = AuditService(db)
    for pid in project_ids:
        service.assign_project(user_id, pid)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=user.id,
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.project_assign,
            recurso="user",
            recurso_id=user_id,
            detalle={"project_id": pid},
            ip_address=request.client.host if request.client else None,
            project_id=pid,
        )
    return {"success": True}


@router.delete("/users/{user_id}/projects/{project_id}")
def unassign_project(
    request: Request,
    user_id: str,
    project_id: int,
    user: User = Depends(require_permission(Permiso.usuarios_gestionar)),
    service: UserService = Depends(get_service),
    db: Session = Depends(get_db),
):
    service.unassign_project(user_id, project_id)

    audit = AuditService(db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=user.id,
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.project_unassign,
        recurso="user",
        recurso_id=user_id,
        detalle={"project_id": project_id},
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    return {"success": True}
