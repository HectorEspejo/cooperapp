from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document import CategoriaDocumento
from app.models.user import User
from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import Permiso
from app.schemas.document import (
    DocumentResponse,
    DocumentCreate,
    DocumentUpdate,
    DocumentSummary,
)
from app.services.document_service import DocumentService

router = APIRouter()


@router.post("/projects/{project_id}/documents", response_model=DocumentResponse)
def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    categoria: CategoriaDocumento = Form(...),
    descripcion: str | None = Form(None),
    user: User = Depends(require_permission(Permiso.documento_subir)),
    db: Session = Depends(get_db),
):
    """Upload a document to a project"""
    service = DocumentService(db)
    data = DocumentCreate(categoria=categoria, descripcion=descripcion)
    try:
        return service.create_document(project_id, file, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/documents", response_model=list[DocumentResponse])
def list_documents(
    project_id: int,
    categoria: CategoriaDocumento | None = None,
    sellado: bool | None = None,
    vinculado: bool | None = None,
    user: User = Depends(require_permission(Permiso.documento_ver)),
    db: Session = Depends(get_db),
):
    """List documents for a project with optional filters"""
    from app.schemas.document import DocumentFilters

    service = DocumentService(db)
    filters = DocumentFilters(categoria=categoria, sellado=sellado, vinculado=vinculado)
    return service.get_project_documents(project_id, filters)


@router.get("/projects/{project_id}/documents/summary", response_model=DocumentSummary)
def get_documents_summary(
    project_id: int,
    user: User = Depends(require_permission(Permiso.documento_ver)),
    db: Session = Depends(get_db),
):
    """Get document statistics for a project"""
    service = DocumentService(db)
    return service.get_document_summary(project_id)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    user: User = Depends(require_permission(Permiso.documento_ver)),
    db: Session = Depends(get_db),
):
    """Get a single document by ID"""
    service = DocumentService(db)
    document = service.get_document_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return document


@router.put("/documents/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: int,
    data: DocumentUpdate,
    user: User = Depends(require_permission(Permiso.documento_subir)),
    db: Session = Depends(get_db),
):
    """Update document metadata"""
    service = DocumentService(db)
    document = service.update_document(document_id, data)
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return document


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    user: User = Depends(require_permission(Permiso.documento_subir)),
    db: Session = Depends(get_db),
):
    """Delete a document"""
    service = DocumentService(db)
    if not service.delete_document(document_id):
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return {"success": True}


@router.get("/documents/{document_id}/download")
def download_document(
    document_id: int,
    user: User = Depends(require_permission(Permiso.documento_ver)),
    db: Session = Depends(get_db),
):
    """Download a document file"""
    import os

    service = DocumentService(db)
    document = service.get_document_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    if not os.path.exists(document.file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado en disco")

    return FileResponse(
        path=document.file_path,
        filename=document.original_filename,
        media_type=document.mime_type or "application/octet-stream",
    )


@router.post("/documents/{document_id}/seal", response_model=DocumentResponse)
def seal_document(
    document_id: int,
    user: User = Depends(require_permission(Permiso.documento_sellar)),
    db: Session = Depends(get_db),
):
    """Seal a document for justification"""
    service = DocumentService(db)
    try:
        document = service.seal_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        return document
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/documents/{document_id}/unseal", response_model=DocumentResponse)
def unseal_document(
    document_id: int,
    user: User = Depends(require_permission(Permiso.documento_sellar)),
    db: Session = Depends(get_db),
):
    """Unseal a document"""
    service = DocumentService(db)
    document = service.unseal_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return document


@router.post("/projects/{project_id}/documents/zip")
def download_documents_zip(
    project_id: int,
    categoria: CategoriaDocumento | None = None,
    user: User = Depends(require_permission(Permiso.documento_ver)),
    db: Session = Depends(get_db),
):
    """Download project documents as ZIP archive"""
    service = DocumentService(db)
    try:
        zip_buffer = service.create_zip_archive(project_id, categoria)
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=documentos_proyecto_{project_id}.zip"
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/documents/seal-all")
def seal_all_documents(
    project_id: int,
    user: User = Depends(require_permission(Permiso.documento_sellar)),
    db: Session = Depends(get_db),
):
    """Seal all unsealed documents for a project"""
    service = DocumentService(db)
    count = service.seal_all_documents(project_id)
    return {"success": True, "sealed_count": count}
