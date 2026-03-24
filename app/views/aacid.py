from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.aacid_service import AACIDFormService
from app.services.aacid_field_map import NARRATIVE_SECTIONS
from app.models.aacid import MARKER_NAMES
from app.services.project_service import ProjectService
from app.auth.dependencies import require_permission
from app.auth.permissions import Permiso


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_aacid_service(db: Session = Depends(get_db)) -> AACIDFormService:
    return AACIDFormService(db)


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


@router.get("/{project_id}/aacid", response_class=HTMLResponse)
def aacid_tab(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.informe_generar)),
    aacid_service: AACIDFormService = Depends(get_aacid_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Render the AACID tab content."""
    project = project_service.get_by_id(project_id)
    if not project:
        return HTMLResponse(content="<p>Proyecto no encontrado</p>", status_code=404)

    aacid_fields = aacid_service.get_project_aacid_fields(project_id)
    narratives = aacid_service.get_narratives(project_id)
    narratives_dict = {n.section_code: n.content for n in narratives}
    beneficiaries = aacid_service.get_beneficiaries(project_id)
    volunteers = aacid_service.get_volunteers(project_id)
    markers = aacid_service.get_markers(project_id)
    markers_dict = {m.marker_name: m.level for m in markers}
    validation = aacid_service.validate(project_id)
    preview = aacid_service.get_preview(project_id)

    return templates.TemplateResponse(
        "partials/projects/aacid_tab.html",
        {
            "request": request,
            "project": project,
            "aacid_fields": aacid_fields,
            "narratives_dict": narratives_dict,
            "beneficiaries": beneficiaries,
            "volunteers": volunteers,
            "markers_dict": markers_dict,
            "validation": validation,
            "preview": preview,
            "narrative_sections": NARRATIVE_SECTIONS,
            "marker_names": MARKER_NAMES,
        },
    )
