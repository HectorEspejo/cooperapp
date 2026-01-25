import os
import shutil
import zipfile
from datetime import datetime
from io import BytesIO
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from fastapi import UploadFile

from app.models.document import Document, CategoriaDocumento, VerificationSource
from app.models.project import Project
from app.schemas.document import (
    DocumentCreate,
    DocumentUpdate,
    DocumentSummary,
    DocumentFilters,
)


class DocumentService:
    def __init__(self, db: Session):
        self.db = db

    # CRUD Operations
    def get_project_documents(
        self, project_id: int, filters: DocumentFilters | None = None
    ) -> list[Document]:
        """Get all documents for a project with optional filters"""
        query = (
            select(Document)
            .where(Document.project_id == project_id)
            .order_by(Document.created_at.desc())
        )

        if filters:
            if filters.categoria:
                query = query.where(Document.categoria == filters.categoria)
            if filters.sellado is not None:
                query = query.where(Document.sellado == filters.sellado)
            if filters.vinculado is not None:
                # Subquery to check if document has verification sources
                has_sources = (
                    select(VerificationSource.document_id)
                    .where(VerificationSource.document_id == Document.id)
                    .exists()
                )
                if filters.vinculado:
                    query = query.where(has_sources)
                else:
                    query = query.where(~has_sources)

        return list(self.db.execute(query).scalars().all())

    def get_document_by_id(self, document_id: int) -> Document | None:
        """Get a single document by ID"""
        return self.db.get(Document, document_id)

    def create_document(
        self, project_id: int, file: UploadFile, data: DocumentCreate
    ) -> Document:
        """Create a new document by uploading a file"""
        # Verify project exists
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError("Proyecto no encontrado")

        # Create directory structure: uploads/{project_id}/documents/{categoria}/
        upload_dir = f"uploads/{project_id}/documents/{data.categoria.value}"
        os.makedirs(upload_dir, exist_ok=True)

        # Generate safe filename
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        original_filename = file.filename or "document"
        safe_filename = original_filename.replace(" ", "_").replace("/", "_")
        filename = f"{timestamp}_{safe_filename}"
        filepath = os.path.join(upload_dir, filename)

        # Get file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to start

        # Save file
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Create document record
        document = Document(
            project_id=project_id,
            filename=filename,
            original_filename=original_filename,
            file_path=filepath,
            file_size=file_size,
            mime_type=file.content_type,
            categoria=data.categoria,
            descripcion=data.descripcion,
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def update_document(self, document_id: int, data: DocumentUpdate) -> Document | None:
        """Update document metadata"""
        document = self.get_document_by_id(document_id)
        if not document:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # If changing category, move file to new directory
        if "categoria" in update_data and update_data["categoria"] != document.categoria:
            old_path = document.file_path
            new_dir = f"uploads/{document.project_id}/documents/{update_data['categoria'].value}"
            os.makedirs(new_dir, exist_ok=True)
            new_path = os.path.join(new_dir, document.filename)

            if os.path.exists(old_path):
                shutil.move(old_path, new_path)
                update_data["file_path"] = new_path

        for field, value in update_data.items():
            setattr(document, field, value)

        self.db.commit()
        self.db.refresh(document)
        return document

    def delete_document(self, document_id: int) -> bool:
        """Delete a document and its file"""
        document = self.get_document_by_id(document_id)
        if not document:
            return False

        # Delete file from disk
        if os.path.exists(document.file_path):
            os.remove(document.file_path)

        self.db.delete(document)
        self.db.commit()
        return True

    # Sealing
    def seal_document(self, document_id: int) -> Document | None:
        """Seal a document for justification"""
        document = self.get_document_by_id(document_id)
        if not document:
            return None

        if document.sellado:
            raise ValueError("El documento ya esta sellado")

        document.sellado = True
        document.fecha_sellado = datetime.utcnow()
        self.db.commit()
        self.db.refresh(document)
        return document

    def unseal_document(self, document_id: int) -> Document | None:
        """Unseal a document (admin only in production)"""
        document = self.get_document_by_id(document_id)
        if not document:
            return None

        document.sellado = False
        document.fecha_sellado = None
        self.db.commit()
        self.db.refresh(document)
        return document

    # Summary
    def get_document_summary(self, project_id: int) -> DocumentSummary:
        """Get document summary statistics for a project"""
        documents = self.get_project_documents(project_id)

        summary = DocumentSummary()
        summary.total = len(documents)

        by_categoria: dict[str, int] = {}
        total_size = 0

        for doc in documents:
            # Count by category
            cat_name = doc.categoria.value
            by_categoria[cat_name] = by_categoria.get(cat_name, 0) + 1

            # Count sealed
            if doc.sellado:
                summary.sellados += 1
            else:
                summary.pendientes_sellar += 1

            # Count linked
            if doc.verification_sources:
                summary.vinculados += 1
            else:
                summary.huerfanos += 1

            total_size += doc.file_size

        summary.by_categoria = by_categoria
        summary.tamano_total = total_size
        summary.tamano_total_human = self._format_size(total_size)

        return summary

    def _format_size(self, size: int) -> str:
        """Format size in bytes to human-readable string"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    # ZIP Archive
    def create_zip_archive(
        self, project_id: int, categoria: CategoriaDocumento | None = None
    ) -> BytesIO:
        """Create a ZIP archive of project documents"""
        filters = DocumentFilters(categoria=categoria) if categoria else None
        documents = self.get_project_documents(project_id, filters)

        if not documents:
            raise ValueError("No hay documentos para descargar")

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for doc in documents:
                if os.path.exists(doc.file_path):
                    # Organize by category in ZIP
                    arcname = f"{doc.categoria.value}/{doc.original_filename}"
                    zip_file.write(doc.file_path, arcname)

        zip_buffer.seek(0)
        return zip_buffer

    # Batch seal
    def seal_all_documents(self, project_id: int) -> int:
        """Seal all unsealed documents for a project"""
        documents = self.get_project_documents(
            project_id, DocumentFilters(sellado=False)
        )

        count = 0
        now = datetime.utcnow()
        for doc in documents:
            doc.sellado = True
            doc.fecha_sellado = now
            count += 1

        self.db.commit()
        return count
