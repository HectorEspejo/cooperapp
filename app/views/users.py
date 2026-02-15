from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User, Rol
from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import Permiso
from app.services.user_service import UserService
from app.services.project_service import ProjectService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


@router.get("/usuarios", response_class=HTMLResponse)
def users_list(
    request: Request,
    rol: str | None = None,
    activo: str | None = None,
    search: str | None = None,
    user: User = Depends(require_permission(Permiso.usuarios_gestionar)),
    user_service: UserService = Depends(get_user_service),
):
    rol_filter = Rol(rol) if rol else None
    activo_filter = activo == "true" if activo is not None else None

    users = user_service.get_all(rol=rol_filter, activo=activo_filter, search=search)
    return templates.TemplateResponse(
        "pages/users/list.html",
        {
            "request": request,
            "users": users,
            "user": user,
            "roles": list(Rol),
            "filters": {"rol": rol, "activo": activo, "search": search},
        },
    )


@router.get("/usuarios/{user_id}", response_class=HTMLResponse)
def user_detail(
    request: Request,
    user_id: str,
    user: User = Depends(require_permission(Permiso.usuarios_gestionar)),
    user_service: UserService = Depends(get_user_service),
    project_service: ProjectService = Depends(get_project_service),
):
    target_user = user_service.get_by_id(user_id)
    if not target_user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    all_projects, _ = project_service.get_all(page=1, page_size=1000)
    assigned_ids = {p.id for p in target_user.assigned_projects}

    return templates.TemplateResponse(
        "pages/users/detail.html",
        {
            "request": request,
            "target_user": target_user,
            "user": user,
            "roles": list(Rol),
            "all_projects": all_projects,
            "assigned_ids": assigned_ids,
        },
    )
