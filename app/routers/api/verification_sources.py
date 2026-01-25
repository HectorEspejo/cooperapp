from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.document import (
    VerificationSourceResponse,
    VerificationSourceCreate,
    VerificationSourceUpdate,
    VerificationSourceSummary,
)
from app.services.verification_source_service import VerificationSourceService

router = APIRouter()


@router.get(
    "/indicators/{indicator_id}/verification-sources",
    response_model=list[VerificationSourceResponse],
)
def list_indicator_sources(
    indicator_id: int,
    db: Session = Depends(get_db),
):
    """List verification sources for an indicator"""
    service = VerificationSourceService(db)
    return service.get_indicator_sources(indicator_id)


@router.get(
    "/indicators/{indicator_id}/verification-sources/summary",
    response_model=VerificationSourceSummary,
)
def get_indicator_sources_summary(
    indicator_id: int,
    db: Session = Depends(get_db),
):
    """Get verification source summary for an indicator"""
    service = VerificationSourceService(db)
    return service.get_indicator_summary(indicator_id)


@router.get(
    "/activities/{activity_id}/verification-sources",
    response_model=list[VerificationSourceResponse],
)
def list_activity_sources(
    activity_id: int,
    db: Session = Depends(get_db),
):
    """List verification sources for an activity"""
    service = VerificationSourceService(db)
    return service.get_activity_sources(activity_id)


@router.get(
    "/activities/{activity_id}/verification-sources/summary",
    response_model=VerificationSourceSummary,
)
def get_activity_sources_summary(
    activity_id: int,
    db: Session = Depends(get_db),
):
    """Get verification source summary for an activity"""
    service = VerificationSourceService(db)
    return service.get_activity_summary(activity_id)


@router.post("/verification-sources", response_model=VerificationSourceResponse)
def create_verification_source(
    data: VerificationSourceCreate,
    db: Session = Depends(get_db),
):
    """Create a new verification source link"""
    service = VerificationSourceService(db)
    try:
        return service.create_source(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/verification-sources/{source_id}", response_model=VerificationSourceResponse)
def get_verification_source(
    source_id: int,
    db: Session = Depends(get_db),
):
    """Get a single verification source by ID"""
    service = VerificationSourceService(db)
    source = service.get_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Fuente de verificacion no encontrada")
    return source


@router.put("/verification-sources/{source_id}", response_model=VerificationSourceResponse)
def update_verification_source(
    source_id: int,
    data: VerificationSourceUpdate,
    db: Session = Depends(get_db),
):
    """Update verification source metadata"""
    service = VerificationSourceService(db)
    source = service.update_source(source_id, data)
    if not source:
        raise HTTPException(status_code=404, detail="Fuente de verificacion no encontrada")
    return source


@router.delete("/verification-sources/{source_id}")
def delete_verification_source(
    source_id: int,
    db: Session = Depends(get_db),
):
    """Delete a verification source link"""
    service = VerificationSourceService(db)
    if not service.delete_source(source_id):
        raise HTTPException(status_code=404, detail="Fuente de verificacion no encontrada")
    return {"success": True}


@router.post("/verification-sources/{source_id}/validate", response_model=VerificationSourceResponse)
def validate_verification_source(
    source_id: int,
    db: Session = Depends(get_db),
):
    """Validate a verification source"""
    service = VerificationSourceService(db)
    try:
        source = service.validate_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Fuente de verificacion no encontrada")
        return source
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verification-sources/{source_id}/unvalidate", response_model=VerificationSourceResponse)
def unvalidate_verification_source(
    source_id: int,
    db: Session = Depends(get_db),
):
    """Remove validation from a verification source"""
    service = VerificationSourceService(db)
    source = service.unvalidate_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Fuente de verificacion no encontrada")
    return source


@router.get("/projects/{project_id}/missing-sources/indicators")
def get_indicators_without_sources(
    project_id: int,
    db: Session = Depends(get_db),
):
    """Get indicators that have no verification sources"""
    service = VerificationSourceService(db)
    indicators = service.get_indicators_without_sources(project_id)
    return [{"id": i.id, "codigo": i.codigo, "descripcion": i.descripcion} for i in indicators]


@router.get("/projects/{project_id}/missing-sources/activities")
def get_activities_without_sources(
    project_id: int,
    db: Session = Depends(get_db),
):
    """Get completed activities that have no verification sources"""
    service = VerificationSourceService(db)
    activities = service.get_activities_without_sources(project_id)
    return [{"id": a.id, "numero": a.numero, "descripcion": a.descripcion} for a in activities]
