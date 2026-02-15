from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.models.user import User
from app.models.audit_log import AccionAuditoria
from app.auth.dependencies import require_permission
from app.auth.permissions import Permiso

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/auditoria", response_class=HTMLResponse)
def audit_index(
    request: Request,
    user: User = Depends(require_permission(Permiso.auditoria_ver)),
):
    return templates.TemplateResponse(
        "pages/audit/index.html",
        {
            "request": request,
            "user": user,
            "acciones": list(AccionAuditoria),
        },
    )
