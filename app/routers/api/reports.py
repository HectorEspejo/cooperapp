import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.report import TipoInforme
from app.services.report_service import ReportService
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
    service: ReportService = Depends(get_service),
):
    """List all reports for a project."""
    reports = service.get_project_reports(project_id)
    return ReportListResponse(items=reports, total=len(reports))


@router.get("/projects/{project_id}/reports/validate", response_model=ReportValidationResult)
def validate_report_generation(
    project_id: int,
    service: ReportService = Depends(get_service),
):
    """Validate project data before generating reports."""
    try:
        return service.validate_for_generation(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/projects/{project_id}/reports/generate", response_model=ReportResponse, status_code=201)
def generate_report(
    project_id: int,
    data: ReportGenerateRequest,
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
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando informe: {str(e)}")


@router.post("/projects/{project_id}/reports/pack", response_model=ReportResponse, status_code=201)
def generate_pack(
    project_id: int,
    data: PackGenerateRequest | None = None,
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
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando pack: {str(e)}")


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: int,
    service: ReportService = Depends(get_service),
):
    """Download a report file."""
    report = service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Informe no encontrado")

    if not os.path.exists(report.ruta):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

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
    report_id: int,
    service: ReportService = Depends(get_service),
):
    """Delete a report."""
    if not service.delete_report(report_id):
        raise HTTPException(status_code=404, detail="Informe no encontrado")
