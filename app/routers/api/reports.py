import os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.report import TipoInforme
from app.models.user import User
from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import Permiso
from app.services.report_service import ReportService
from app.services.audit_service import AuditService
from app.models.audit_log import ActorType, AccionAuditoria
from app.schemas.report import (
    ReportResponse,
    ReportListResponse,
    ReportValidationResult,
    ReportGenerateRequest,
    PackGenerateRequest,
)


router = APIRouter()


def get_service(db: Session = Depends(get_db)) -> ReportService:
    return ReportService(db)


@router.get("/projects/{project_id}/reports", response_model=ReportListResponse)
def list_project_reports(
    project_id: int,
    user: User = Depends(require_permission(Permiso.informe_generar)),
    service: ReportService = Depends(get_service),
):
    """List all reports for a project."""
    reports = service.get_project_reports(project_id)
    return ReportListResponse(items=reports, total=len(reports))


@router.get("/projects/{project_id}/reports/validate", response_model=ReportValidationResult)
def validate_report_generation(
    project_id: int,
    user: User = Depends(require_permission(Permiso.informe_generar)),
    service: ReportService = Depends(get_service),
):
    """Validate project data before generating reports."""
    try:
        return service.validate_for_generation(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/projects/{project_id}/reports/generate", response_model=ReportResponse, status_code=201)
def generate_report(
    request: Request,
    project_id: int,
    data: ReportGenerateRequest,
    user: User = Depends(require_permission(Permiso.informe_generar)),
    service: ReportService = Depends(get_service),
):
    """Generate a single report."""
    try:
        report = service.generate_report(
            project_id=project_id,
            tipo=data.tipo,
            periodo=data.periodo,
            generado_por=data.generado_por,
        )

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
            detalle={"tipo": data.tipo.value, "periodo": data.periodo},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )

        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando informe: {str(e)}")


@router.post("/projects/{project_id}/reports/pack", response_model=ReportResponse, status_code=201)
def generate_pack(
    request: Request,
    project_id: int,
    data: PackGenerateRequest | None = None,
    user: User = Depends(require_permission(Permiso.informe_generar)),
    service: ReportService = Depends(get_service),
):
    """Generate a ZIP pack with multiple reports."""
    try:
        tipos = data.tipos if data else None
        generado_por = data.generado_por if data else None
        report = service.generate_pack(
            project_id=project_id,
            tipos=tipos,
            generado_por=generado_por,
        )

        # Audit log
        audit = AuditService(service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.export,
            recurso="report_pack",
            recurso_id=str(report.id),
            detalle={"tipos": [t.value for t in tipos] if tipos else "all"},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )

        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando pack: {str(e)}")


@router.get("/reports/{report_id}/download")
def download_report(
    request: Request,
    report_id: int,
    user: User = Depends(require_permission(Permiso.informe_descargar)),
    service: ReportService = Depends(get_service),
):
    """Download a report file."""
    report = service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Informe no encontrado")

    if not os.path.exists(report.ruta):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    # Audit log
    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.download,
        recurso="report",
        recurso_id=str(report_id),
        detalle={"nombre": report.nombre_archivo},
        ip_address=request.client.host if request.client else None,
        project_id=report.project_id,
    )

    # Determine media type
    if report.nombre_archivo.endswith(".xlsx"):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif report.nombre_archivo.endswith(".zip"):
        media_type = "application/zip"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        path=report.ruta,
        filename=report.nombre_archivo,
        media_type=media_type,
    )


@router.delete("/reports/{report_id}", status_code=204)
def delete_report(
    request: Request,
    report_id: int,
    user: User = Depends(require_permission(Permiso.informe_generar)),
    service: ReportService = Depends(get_service),
):
    """Delete a report."""
    report = service.get_report_by_id(report_id)
    if not service.delete_report(report_id):
        raise HTTPException(status_code=404, detail="Informe no encontrado")

    # Audit log
    audit = AuditService(service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.delete,
        recurso="report",
        recurso_id=str(report_id),
        detalle=None,
        ip_address=request.client.host if request.client else None,
        project_id=report.project_id if report else None,
    )
