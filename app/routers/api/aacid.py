import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import Permiso
from app.services.aacid_service import AACIDFormService
from app.services.audit_service import AuditService
from app.models.audit_log import ActorType, AccionAuditoria
from app.schemas.aacid import (
    ProjectAACIDFieldsUpdate,
    ProjectAACIDFieldsResponse,
    NarrativeUpsert,
    NarrativeResponse,
    BeneficiaryUpdate,
    BeneficiaryResponse,
    VolunteerUpdate,
    VolunteerResponse,
    MarkerUpdate,
    MarkerResponse,
    AACIDValidationResult,
    AACIDPreviewResponse,
)


router = APIRouter()


def get_service(db: Session = Depends(get_db)) -> AACIDFormService:
    return AACIDFormService(db)


# ---- Campos AACID del proyecto ----


@router.get("/projects/{project_id}/aacid/fields", response_model=ProjectAACIDFieldsResponse)
def get_aacid_fields(
    project_id: int,
    user: User = Depends(require_permission(Permiso.proyecto_ver)),
    service: AACIDFormService = Depends(get_service),
):
    try:
        return service.get_project_aacid_fields(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/projects/{project_id}/aacid/fields", response_model=ProjectAACIDFieldsResponse)
def update_aacid_fields(
    project_id: int,
    data: ProjectAACIDFieldsUpdate,
    user: User = Depends(require_permission(Permiso.proyecto_editar)),
    service: AACIDFormService = Depends(get_service),
):
    try:
        service.update_project_aacid_fields(project_id, data.model_dump(exclude_unset=True))
        return service.get_project_aacid_fields(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---- Narrativas ----


@router.get("/projects/{project_id}/aacid/narratives", response_model=list[NarrativeResponse])
def list_narratives(
    project_id: int,
    user: User = Depends(require_permission(Permiso.proyecto_ver)),
    service: AACIDFormService = Depends(get_service),
):
    return service.get_narratives(project_id)


@router.put("/projects/{project_id}/aacid/narratives/{section_code}")
def upsert_narrative(
    project_id: int,
    section_code: str,
    data: NarrativeUpsert,
    user: User = Depends(require_permission(Permiso.proyecto_editar)),
    service: AACIDFormService = Depends(get_service),
):
    try:
        narrative = service.upsert_narrative(project_id, section_code, data.content)
        return NarrativeResponse.model_validate(narrative)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---- Beneficiarios ----


@router.get("/projects/{project_id}/aacid/beneficiaries")
def get_beneficiaries(
    project_id: int,
    user: User = Depends(require_permission(Permiso.proyecto_ver)),
    service: AACIDFormService = Depends(get_service),
):
    result = service.get_beneficiaries(project_id)
    if result:
        return BeneficiaryResponse.model_validate(result)
    return {"women_direct": 0, "men_direct": 0, "total_direct": 0, "target_groups": None}


@router.put("/projects/{project_id}/aacid/beneficiaries", response_model=BeneficiaryResponse)
def upsert_beneficiaries(
    project_id: int,
    data: BeneficiaryUpdate,
    user: User = Depends(require_permission(Permiso.proyecto_editar)),
    service: AACIDFormService = Depends(get_service),
):
    try:
        result = service.upsert_beneficiaries(project_id, data.model_dump())
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---- Voluntarios ----


@router.get("/projects/{project_id}/aacid/volunteers")
def get_volunteers(
    project_id: int,
    user: User = Depends(require_permission(Permiso.proyecto_ver)),
    service: AACIDFormService = Depends(get_service),
):
    result = service.get_volunteers(project_id)
    if result:
        return VolunteerResponse.model_validate(result)
    return {"women": 0, "men": 0, "total": 0}


@router.put("/projects/{project_id}/aacid/volunteers", response_model=VolunteerResponse)
def upsert_volunteers(
    project_id: int,
    data: VolunteerUpdate,
    user: User = Depends(require_permission(Permiso.proyecto_editar)),
    service: AACIDFormService = Depends(get_service),
):
    try:
        result = service.upsert_volunteers(project_id, data.model_dump())
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---- Marcadores ----


@router.get("/projects/{project_id}/aacid/markers", response_model=list[MarkerResponse])
def list_markers(
    project_id: int,
    user: User = Depends(require_permission(Permiso.proyecto_ver)),
    service: AACIDFormService = Depends(get_service),
):
    return service.get_markers(project_id)


@router.put("/projects/{project_id}/aacid/markers/{marker_name}", response_model=MarkerResponse)
def upsert_marker(
    project_id: int,
    marker_name: str,
    data: MarkerUpdate,
    user: User = Depends(require_permission(Permiso.proyecto_editar)),
    service: AACIDFormService = Depends(get_service),
):
    try:
        return service.upsert_marker(project_id, marker_name, data.level)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---- Validacion, preview, generacion ----


@router.get("/projects/{project_id}/aacid/validate", response_model=AACIDValidationResult)
def validate_form(
    project_id: int,
    user: User = Depends(require_permission(Permiso.informe_generar)),
    service: AACIDFormService = Depends(get_service),
):
    try:
        return service.validate(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/projects/{project_id}/aacid/preview", response_model=AACIDPreviewResponse)
def preview_form(
    project_id: int,
    user: User = Depends(require_permission(Permiso.informe_generar)),
    service: AACIDFormService = Depends(get_service),
):
    try:
        return service.get_preview(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/projects/{project_id}/aacid/generate", status_code=201)
def generate_form(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.informe_generar)),
    service: AACIDFormService = Depends(get_service),
):
    try:
        validation = service.validate(project_id)
        if not validation["valid"]:
            raise HTTPException(status_code=400, detail=validation)

        report = service.generate_pdf(project_id, generado_por=user.nombre_completo)

        # Audit log
        audit = AuditService(service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.export,
            recurso="report",
            recurso_id=str(report.id),
            detalle={"tipo": "anexo_iia"},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )

        return {
            "id": report.id,
            "nombre_archivo": report.nombre_archivo,
            "ruta": report.ruta,
            "download_url": f"/api/reports/{report.id}/download",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando Anexo II A: {str(e)}")
