from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.report import TIPO_INFORME_NOMBRES
from app.models.user import User
from app.services.report_service import ReportService
from app.services.project_service import ProjectService
from app.auth.dependencies import require_permission
from app.auth.permissions import Permiso


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_report_service(db: Session = Depends(get_db)) -> ReportService:
    return ReportService(db)


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


@router.get("/{project_id}/reports", response_class=HTMLResponse)
def reports_tab(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.informe_generar)),
    report_service: ReportService = Depends(get_report_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Render the reports tab content."""
    project = project_service.get_by_id(project_id)
    if not project:
        return HTMLResponse(content="<p>Proyecto no encontrado</p>", status_code=404)

    reports = report_service.get_project_reports(project_id)
    validation = report_service.validate_for_generation(project_id)
    report_types = report_service.get_available_report_types(project_id)

    return templates.TemplateResponse(
        "partials/projects/reports_tab.html",
        {
            "request": request,
            "project": project,
            "reports": reports,
            "validation": validation,
            "report_types": report_types,
            "tipo_nombres": TIPO_INFORME_NOMBRES,
        },
    )
