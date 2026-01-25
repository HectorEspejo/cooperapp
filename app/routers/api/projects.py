from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.project import EstadoProyecto, TipoProyecto
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
    ProjectStats,
)
from app.services.project_service import ProjectService

router = APIRouter()


def get_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


@router.get("", response_model=ProjectListResponse)
def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    estado: EstadoProyecto | None = None,
    tipo: TipoProyecto | None = None,
    pais: str | None = None,
    search: str | None = None,
    service: ProjectService = Depends(get_service),
):
    projects, total = service.get_all(
        page=page,
        page_size=page_size,
        estado=estado,
        tipo=tipo,
        pais=pais,
        search=search,
    )
    total_pages = (total + page_size - 1) // page_size
    return ProjectListResponse(
        items=projects,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/stats", response_model=ProjectStats)
def get_stats(service: ProjectService = Depends(get_service)):
    return service.get_stats()


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    service: ProjectService = Depends(get_service),
):
    project = service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return project


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    data: ProjectCreate,
    service: ProjectService = Depends(get_service),
):
    existing = service.get_by_codigo_contable(data.codigo_contable)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe un proyecto con código contable {data.codigo_contable}",
        )
    return service.create(data)


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    data: ProjectUpdate,
    service: ProjectService = Depends(get_service),
):
    # Check if updating codigo_contable to existing one
    if data.codigo_contable:
        existing = service.get_by_codigo_contable(data.codigo_contable)
        if existing and existing.id != project_id:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe un proyecto con código contable {data.codigo_contable}",
            )

    project = service.update(project_id, data)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: int,
    service: ProjectService = Depends(get_service),
):
    if not service.delete(project_id):
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
