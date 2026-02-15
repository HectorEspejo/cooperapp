from fastapi import Depends, Request, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User, Rol, user_project
from app.models.counterpart_session import CounterpartSession
from app.auth.permissions import Permiso, PERMISOS_POR_ROL
from datetime import datetime


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="No autenticado")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    if not user.activo:
        raise HTTPException(status_code=403, detail="Cuenta desactivada")

    if not user.rol:
        raise HTTPException(status_code=403, detail="Cuenta pendiente de activacion")

    return user


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.activo:
        return None
    return user


def require_permission(permiso: Permiso):
    def _check(user: User = Depends(get_current_user)):
        if not user.rol:
            raise HTTPException(status_code=403, detail="Sin rol asignado")
        if permiso not in PERMISOS_POR_ROL.get(user.rol, set()):
            raise HTTPException(status_code=403, detail="Sin permisos suficientes")
        return user
    return _check


def check_project_access(request: Request, project_id: int, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="No autenticado")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.activo or not user.rol:
        raise HTTPException(status_code=403, detail="Sin acceso")

    # Directors, coordinadores and tecnicos can see all projects
    if user.rol in (Rol.director, Rol.coordinador, Rol.tecnico_sede):
        return user

    # Gestor pais: only assigned projects
    if user.rol == Rol.gestor_pais:
        assigned = db.execute(
            user_project.select().where(
                user_project.c.user_id == user.id,
                user_project.c.project_id == project_id,
            )
        ).first()
        if not assigned:
            raise HTTPException(status_code=403, detail="No tienes acceso a este proyecto")

    return user


def get_current_counterpart(request: Request, db: Session = Depends(get_db)) -> CounterpartSession:
    token = request.cookies.get("counterpart_token")
    if not token:
        raise HTTPException(status_code=401, detail="Sesion de contraparte no encontrada")

    session = db.query(CounterpartSession).filter(
        CounterpartSession.session_token == token
    ).first()

    if not session or not session.is_valid:
        raise HTTPException(status_code=401, detail="Sesion expirada o invalida")

    # Update last activity
    session.last_activity = datetime.utcnow()
    db.commit()

    return session
