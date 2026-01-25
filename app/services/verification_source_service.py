from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.document import Document, VerificationSource, TipoFuenteVerificacion
from app.models.logical_framework import Indicator, Activity
from app.schemas.document import (
    VerificationSourceCreate,
    VerificationSourceUpdate,
    VerificationSourceSummary,
)


class VerificationSourceService:
    def __init__(self, db: Session):
        self.db = db

    # CRUD Operations
    def get_indicator_sources(self, indicator_id: int) -> list[VerificationSource]:
        """Get all verification sources for an indicator"""
        query = (
            select(VerificationSource)
            .options(joinedload(VerificationSource.document))
            .where(VerificationSource.indicator_id == indicator_id)
            .order_by(VerificationSource.created_at.desc())
        )
        return list(self.db.execute(query).scalars().all())

    def get_activity_sources(self, activity_id: int) -> list[VerificationSource]:
        """Get all verification sources for an activity"""
        query = (
            select(VerificationSource)
            .options(joinedload(VerificationSource.document))
            .where(VerificationSource.activity_id == activity_id)
            .order_by(VerificationSource.created_at.desc())
        )
        return list(self.db.execute(query).scalars().all())

    def get_source_by_id(self, source_id: int) -> VerificationSource | None:
        """Get a single verification source by ID"""
        query = (
            select(VerificationSource)
            .options(joinedload(VerificationSource.document))
            .where(VerificationSource.id == source_id)
        )
        return self.db.execute(query).scalar_one_or_none()

    def create_source(self, data: VerificationSourceCreate) -> VerificationSource:
        """Create a new verification source link"""
        # Verify document exists
        document = self.db.get(Document, data.document_id)
        if not document:
            raise ValueError("Documento no encontrado")

        # Verify exactly one target is set
        if data.indicator_id and data.activity_id:
            raise ValueError("Solo se puede vincular a un indicador O una actividad, no ambos")
        if not data.indicator_id and not data.activity_id:
            raise ValueError("Debe especificar un indicador o una actividad")

        # Verify target exists
        if data.indicator_id:
            indicator = self.db.get(Indicator, data.indicator_id)
            if not indicator:
                raise ValueError("Indicador no encontrado")
        else:
            activity = self.db.get(Activity, data.activity_id)
            if not activity:
                raise ValueError("Actividad no encontrada")

        # Check for duplicate link
        existing_query = select(VerificationSource).where(
            VerificationSource.document_id == data.document_id
        )
        if data.indicator_id:
            existing_query = existing_query.where(
                VerificationSource.indicator_id == data.indicator_id
            )
        else:
            existing_query = existing_query.where(
                VerificationSource.activity_id == data.activity_id
            )

        existing = self.db.execute(existing_query).scalar_one_or_none()
        if existing:
            raise ValueError("Este documento ya esta vinculado a este elemento")

        source = VerificationSource(
            document_id=data.document_id,
            indicator_id=data.indicator_id,
            activity_id=data.activity_id,
            tipo=data.tipo,
            descripcion=data.descripcion,
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def update_source(
        self, source_id: int, data: VerificationSourceUpdate
    ) -> VerificationSource | None:
        """Update verification source metadata"""
        source = self.get_source_by_id(source_id)
        if not source:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(source, field, value)

        self.db.commit()
        self.db.refresh(source)
        return source

    def delete_source(self, source_id: int) -> bool:
        """Delete a verification source link"""
        source = self.db.get(VerificationSource, source_id)
        if not source:
            return False

        self.db.delete(source)
        self.db.commit()
        return True

    # Validation
    def validate_source(self, source_id: int) -> VerificationSource | None:
        """Validate a verification source"""
        source = self.get_source_by_id(source_id)
        if not source:
            return None

        if source.validado:
            raise ValueError("La fuente de verificacion ya esta validada")

        source.validado = True
        source.fecha_validacion = datetime.utcnow()
        self.db.commit()
        self.db.refresh(source)
        return source

    def unvalidate_source(self, source_id: int) -> VerificationSource | None:
        """Remove validation from a verification source"""
        source = self.get_source_by_id(source_id)
        if not source:
            return None

        source.validado = False
        source.fecha_validacion = None
        self.db.commit()
        self.db.refresh(source)
        return source

    # Summary
    def get_indicator_summary(self, indicator_id: int) -> VerificationSourceSummary:
        """Get verification source summary for an indicator"""
        sources = self.get_indicator_sources(indicator_id)
        return self._build_summary(sources)

    def get_activity_summary(self, activity_id: int) -> VerificationSourceSummary:
        """Get verification source summary for an activity"""
        sources = self.get_activity_sources(activity_id)
        return self._build_summary(sources)

    def _build_summary(self, sources: list[VerificationSource]) -> VerificationSourceSummary:
        """Build summary from list of sources"""
        summary = VerificationSourceSummary()
        summary.total = len(sources)

        by_tipo: dict[str, int] = {}
        for source in sources:
            if source.validado:
                summary.validados += 1
            else:
                summary.pendientes += 1

            tipo_name = source.tipo.value
            by_tipo[tipo_name] = by_tipo.get(tipo_name, 0) + 1

        summary.by_tipo = by_tipo
        return summary

    # Alerts for missing sources
    def get_indicators_without_sources(self, project_id: int) -> list[Indicator]:
        """Get indicators that have no verification sources"""
        from app.models.logical_framework import LogicalFramework

        # Get project's framework
        framework = self.db.execute(
            select(LogicalFramework).where(LogicalFramework.project_id == project_id)
        ).scalar_one_or_none()

        if not framework:
            return []

        # Get indicators without verification sources
        query = (
            select(Indicator)
            .where(Indicator.framework_id == framework.id)
            .where(
                ~select(VerificationSource.id)
                .where(VerificationSource.indicator_id == Indicator.id)
                .exists()
            )
        )
        return list(self.db.execute(query).scalars().all())

    def get_activities_without_sources(self, project_id: int) -> list[Activity]:
        """Get completed activities that have no verification sources"""
        from app.models.logical_framework import LogicalFramework, EstadoActividad

        # Get project's framework
        framework = self.db.execute(
            select(LogicalFramework).where(LogicalFramework.project_id == project_id)
        ).scalar_one_or_none()

        if not framework:
            return []

        # Get completed activities without verification sources
        query = (
            select(Activity)
            .join(Activity.result)
            .where(
                Activity.estado == EstadoActividad.completada,
                ~select(VerificationSource.id)
                .where(VerificationSource.activity_id == Activity.id)
                .exists()
            )
        )
        return list(self.db.execute(query).scalars().all())

    # Get available documents for linking
    def get_available_documents(self, project_id: int) -> list[Document]:
        """Get documents that can be linked as verification sources"""
        query = (
            select(Document)
            .where(Document.project_id == project_id)
            .order_by(Document.created_at.desc())
        )
        return list(self.db.execute(query).scalars().all())
