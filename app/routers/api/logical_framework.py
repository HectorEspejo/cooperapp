from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.logical_framework_service import LogicalFrameworkService
from app.schemas.logical_framework import (
    LogicalFrameworkUpdate, LogicalFrameworkDetailResponse,
    SpecificObjectiveCreate, SpecificObjectiveUpdate, SpecificObjectiveDetailResponse,
    ResultCreate, ResultUpdate, ResultDetailResponse,
    ActivityCreate, ActivityUpdate, ActivityDetailResponse,
    IndicatorCreate, IndicatorUpdate, IndicatorDetailResponse, IndicatorResponse,
    IndicatorUpdateCreate, IndicatorUpdateResponse,
    FrameworkSummary
)

router = APIRouter()


def get_service(db: Session = Depends(get_db)) -> LogicalFrameworkService:
    return LogicalFrameworkService(db)


# ======================== Framework Endpoints ========================

@router.get("/projects/{project_id}/framework", response_model=LogicalFrameworkDetailResponse | None)
def get_framework(
    project_id: int,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Get the full logical framework for a project"""
    return service.get_framework_by_project(project_id)


@router.put("/projects/{project_id}/framework", response_model=LogicalFrameworkDetailResponse)
def create_or_update_framework(
    project_id: int,
    data: LogicalFrameworkUpdate,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Create or update the logical framework for a project"""
    framework = service.create_or_update_framework(project_id, data)
    return service.get_framework_by_project(project_id)


@router.get("/projects/{project_id}/framework/summary", response_model=FrameworkSummary)
def get_framework_summary(
    project_id: int,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Get summary statistics for a framework"""
    return service.get_framework_summary(project_id)


# ======================== Objective Endpoints ========================

@router.post("/projects/{project_id}/framework/objectives", response_model=SpecificObjectiveDetailResponse)
def add_objective(
    project_id: int,
    data: SpecificObjectiveCreate,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Add a specific objective to a project's framework"""
    objective = service.add_objective(project_id, data)
    return service.get_objective(objective.id)


@router.get("/objectives/{objective_id}", response_model=SpecificObjectiveDetailResponse)
def get_objective(
    objective_id: int,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Get a specific objective with its children"""
    objective = service.get_objective(objective_id)
    if not objective:
        raise HTTPException(status_code=404, detail="Objetivo no encontrado")
    return objective


@router.put("/objectives/{objective_id}", response_model=SpecificObjectiveDetailResponse)
def update_objective(
    objective_id: int,
    data: SpecificObjectiveUpdate,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Update a specific objective"""
    objective = service.update_objective(objective_id, data)
    if not objective:
        raise HTTPException(status_code=404, detail="Objetivo no encontrado")
    return service.get_objective(objective_id)


@router.delete("/objectives/{objective_id}")
def delete_objective(
    objective_id: int,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Delete a specific objective and all its children"""
    if not service.delete_objective(objective_id):
        raise HTTPException(status_code=404, detail="Objetivo no encontrado")
    return {"status": "deleted"}


# ======================== Result Endpoints ========================

@router.post("/objectives/{objective_id}/results", response_model=ResultDetailResponse)
def add_result(
    objective_id: int,
    data: ResultCreate,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Add a result to a specific objective"""
    result = service.add_result(objective_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Objetivo no encontrado")
    return service.get_result(result.id)


@router.get("/results/{result_id}", response_model=ResultDetailResponse)
def get_result(
    result_id: int,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Get a result with its children"""
    result = service.get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Resultado no encontrado")
    return result


@router.put("/results/{result_id}", response_model=ResultDetailResponse)
def update_result(
    result_id: int,
    data: ResultUpdate,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Update a result"""
    result = service.update_result(result_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Resultado no encontrado")
    return service.get_result(result_id)


@router.delete("/results/{result_id}")
def delete_result(
    result_id: int,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Delete a result and all its children"""
    if not service.delete_result(result_id):
        raise HTTPException(status_code=404, detail="Resultado no encontrado")
    return {"status": "deleted"}


# ======================== Activity Endpoints ========================

@router.post("/results/{result_id}/activities", response_model=ActivityDetailResponse)
def add_activity(
    result_id: int,
    data: ActivityCreate,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Add an activity to a result"""
    activity = service.add_activity(result_id, data)
    if not activity:
        raise HTTPException(status_code=404, detail="Resultado no encontrado")
    return service.get_activity(activity.id)


@router.get("/activities/{activity_id}", response_model=ActivityDetailResponse)
def get_activity(
    activity_id: int,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Get an activity with its indicators"""
    activity = service.get_activity(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    return activity


@router.put("/activities/{activity_id}", response_model=ActivityDetailResponse)
def update_activity(
    activity_id: int,
    data: ActivityUpdate,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Update an activity (auto-sets dates on status change)"""
    activity = service.update_activity(activity_id, data)
    if not activity:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    return service.get_activity(activity_id)


@router.delete("/activities/{activity_id}")
def delete_activity(
    activity_id: int,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Delete an activity"""
    if not service.delete_activity(activity_id):
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    return {"status": "deleted"}


# ======================== Indicator Endpoints ========================

@router.post("/indicators", response_model=IndicatorResponse)
def create_indicator(
    data: IndicatorCreate,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Create an indicator at any level"""
    return service.create_indicator(data)


@router.get("/indicators/{indicator_id}", response_model=IndicatorDetailResponse)
def get_indicator(
    indicator_id: int,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Get an indicator with its history"""
    indicator = service.get_indicator(indicator_id)
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")
    return indicator


@router.put("/indicators/{indicator_id}", response_model=IndicatorResponse)
def update_indicator(
    indicator_id: int,
    data: IndicatorUpdate,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Update indicator metadata"""
    indicator = service.update_indicator(indicator_id, data)
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")
    return indicator


@router.delete("/indicators/{indicator_id}")
def delete_indicator(
    indicator_id: int,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Delete an indicator"""
    if not service.delete_indicator(indicator_id):
        raise HTTPException(status_code=404, detail="Indicador no encontrado")
    return {"status": "deleted"}


@router.post("/indicators/{indicator_id}/update", response_model=IndicatorResponse)
def update_indicator_value(
    indicator_id: int,
    data: IndicatorUpdateCreate,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Update indicator value and create audit log"""
    indicator = service.update_indicator_value(indicator_id, data)
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")
    return indicator


@router.get("/indicators/{indicator_id}/history", response_model=list[IndicatorUpdateResponse])
def get_indicator_history(
    indicator_id: int,
    service: LogicalFrameworkService = Depends(get_service)
):
    """Get the update history for an indicator"""
    indicator = service.get_indicator(indicator_id)
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")
    return service.get_indicator_history(indicator_id)
