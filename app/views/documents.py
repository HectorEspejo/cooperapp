from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.document import CategoriaDocumento, CATEGORIA_NOMBRES
from app.models.user import User
from app.services.document_service import DocumentService
from app.services.project_service import ProjectService
from app.schemas.document import DocumentCreate, DocumentFilters
from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import Permiso
from app.services.audit_service import AuditService
from app.models.audit_log import ActorType, AccionAuditoria

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    return DocumentService(db)


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


@router.get("/{project_id}/documents", response_class=HTMLResponse)
def documents_tab(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.documento_ver)),
    document_service: DocumentService = Depends(get_document_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Render the documents tab content"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    documents = document_service.get_project_documents(project_id)
    summary = document_service.get_document_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/documents_tab.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "documents": documents,
            "summary": summary,
            "categorias": CategoriaDocumento,
            "categoria_nombres": CATEGORIA_NOMBRES,
        },
    )


@router.get("/{project_id}/documents/table", response_class=HTMLResponse)
def documents_table(
    request: Request,
    project_id: int,
    user: User = Depends(require_permission(Permiso.documento_ver)),
    categoria: str | None = Query(None),
    sellado: str | None = Query(None),
    vinculado: str | None = Query(None),
    document_service: DocumentService = Depends(get_document_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Render filtered documents table"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    filters = DocumentFilters(
        categoria=CategoriaDocumento(categoria) if categoria else None,
        sellado=sellado == "true" if sellado else None,
        vinculado=vinculado == "true" if vinculado else None,
    )

    documents = document_service.get_project_documents(project_id, filters)

    return templates.TemplateResponse(
        "partials/projects/documents_table.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "documents": documents,
            "categoria_nombres": CATEGORIA_NOMBRES,
        },
    )


@router.post("/{project_id}/documents", response_class=HTMLResponse)
async def upload_document(
    request: Request,
    project_id: int,
    file: UploadFile = File(...),
    categoria: CategoriaDocumento = Form(...),
    descripcion: str | None = Form(None),
    user: User = Depends(require_permission(Permiso.documento_subir)),
    document_service: DocumentService = Depends(get_document_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Upload a document and return updated tab"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    try:
        data = DocumentCreate(categoria=categoria, descripcion=descripcion)
        document = document_service.create_document(project_id, file, data)

        # Audit log
        audit = AuditService(document_service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.upload,
            recurso="document",
            recurso_id=str(document.id),
            detalle={"filename": file.filename, "categoria": categoria.value},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Return updated tab content
    documents = document_service.get_project_documents(project_id)
    summary = document_service.get_document_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/documents_tab.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "documents": documents,
            "summary": summary,
            "categorias": CategoriaDocumento,
            "categoria_nombres": CATEGORIA_NOMBRES,
        },
    )


@router.delete("/{project_id}/documents/{document_id}", response_class=HTMLResponse)
def delete_document(
    request: Request,
    project_id: int,
    document_id: int,
    user: User = Depends(require_permission(Permiso.documento_subir)),
    document_service: DocumentService = Depends(get_document_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Delete a document and return updated tab"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    if not document_service.delete_document(document_id):
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    # Audit log
    audit = AuditService(document_service.db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=str(user.id),
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.delete,
        recurso="document",
        recurso_id=str(document_id),
        detalle=None,
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    # Return updated tab content
    documents = document_service.get_project_documents(project_id)
    summary = document_service.get_document_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/documents_tab.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "documents": documents,
            "summary": summary,
            "categorias": CategoriaDocumento,
            "categoria_nombres": CATEGORIA_NOMBRES,
        },
    )


@router.post("/{project_id}/documents/{document_id}/seal", response_class=HTMLResponse)
def seal_document(
    request: Request,
    project_id: int,
    document_id: int,
    user: User = Depends(require_permission(Permiso.documento_sellar)),
    document_service: DocumentService = Depends(get_document_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Seal a document and return updated tab"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    try:
        document_service.seal_document(document_id)

        # Audit log
        audit = AuditService(document_service.db)
        audit.log(
            actor_type=ActorType.internal,
            actor_id=str(user.id),
            actor_email=user.email,
            actor_label=user.nombre_completo,
            accion=AccionAuditoria.status_change,
            recurso="document",
            recurso_id=str(document_id),
            detalle={"accion": "sellar"},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Return updated tab content
    documents = document_service.get_project_documents(project_id)
    summary = document_service.get_document_summary(project_id)

    return templates.TemplateResponse(
        "partials/projects/documents_tab.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "documents": documents,
            "summary": summary,
            "categorias": CategoriaDocumento,
            "categoria_nombres": CATEGORIA_NOMBRES,
        },
    )


@router.get("/{project_id}/documents/{document_id}/preview", response_class=HTMLResponse)
def preview_document(
    request: Request,
    project_id: int,
    document_id: int,
    user: User = Depends(require_permission(Permiso.documento_ver)),
    document_service: DocumentService = Depends(get_document_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Render document preview modal"""
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    document = document_service.get_document_by_id(document_id)
    if not document or document.project_id != project_id:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    return templates.TemplateResponse(
        "partials/projects/document_preview_modal.html",
        {
            "request": request,
            "project": project,
            "document": document,
            "categoria_nombres": CATEGORIA_NOMBRES,
        },
    )
