import os
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.report import Report, TipoInforme, TIPO_INFORME_NOMBRES
from app.models.project import Project
from app.models.expense import Expense, EstadoGasto
from app.models.transfer import Transfer, EstadoTransferencia
from app.schemas.report import (
    ReportCreate,
    ReportValidationResult,
    ReportValidationWarning,
)
from app.services.excel_generator_service import ExcelGeneratorService


EXPORTS_DIR = "exports"


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self._excel_generator = None

    @property
    def excel_generator(self) -> ExcelGeneratorService:
        if self._excel_generator is None:
            self._excel_generator = ExcelGeneratorService(self.db)
        return self._excel_generator

    # CRUD Operations

    def get_project_reports(self, project_id: int) -> list[Report]:
        """Get all reports for a project."""
        query = (
            select(Report)
            .where(Report.project_id == project_id)
            .order_by(Report.created_at.desc())
        )
        return list(self.db.execute(query).scalars().all())

    def get_report_by_id(self, report_id: int) -> Report | None:
        """Get a single report by ID."""
        return self.db.get(Report, report_id)

    def delete_report(self, report_id: int) -> bool:
        """Delete a report and its file."""
        report = self.get_report_by_id(report_id)
        if not report:
            return False

        # Delete file from disk
        if os.path.exists(report.ruta):
            os.remove(report.ruta)

        self.db.delete(report)
        self.db.commit()
        return True

    # Validation

    def validate_for_generation(self, project_id: int) -> ReportValidationResult:
        """Check for potential issues before generating reports."""
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError("Proyecto no encontrado")

        result = ReportValidationResult()

        # Check for draft/pending expenses
        draft_expenses = [
            e for e in project.expenses
            if e.estado in (EstadoGasto.borrador, EstadoGasto.pendiente_revision)
        ]
        if draft_expenses:
            result.warnings.append(
                ReportValidationWarning(
                    tipo="expense",
                    mensaje="Hay gastos en borrador o pendientes de revision que no se incluiran",
                    count=len(draft_expenses),
                )
            )

        # Check for incomplete transfers
        incomplete_transfers = [
            t for t in project.transfers
            if t.estado in (
                EstadoTransferencia.solicitada,
                EstadoTransferencia.aprobada,
                EstadoTransferencia.emitida,
            )
        ]
        if incomplete_transfers:
            result.warnings.append(
                ReportValidationWarning(
                    tipo="transfer",
                    mensaje="Hay transferencias pendientes de recibir",
                    count=len(incomplete_transfers),
                )
            )

        # Check for indicators without recent updates
        if project.logical_framework:
            indicators_without_update = []
            for so in project.logical_framework.specific_objectives:
                for result_obj in so.results:
                    for indicator in result_obj.indicators:
                        if not indicator.updates:
                            indicators_without_update.append(indicator)
            if indicators_without_update:
                result.warnings.append(
                    ReportValidationWarning(
                        tipo="indicator",
                        mensaje="Hay indicadores sin actualizaciones registradas",
                        count=len(indicators_without_update),
                    )
                )

        return result

    # Report Generation

    def generate_report(
        self,
        project_id: int,
        tipo: TipoInforme,
        periodo: str | None = None,
        generado_por: str | None = None,
    ) -> Report:
        """Generate a single report and save it to disk."""
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError("Proyecto no encontrado")

        # Generate the Excel file
        buffer, filename = self.excel_generator.generate_report(project, tipo, periodo)

        # Save to disk
        project_dir = os.path.join(EXPORTS_DIR, str(project_id))
        os.makedirs(project_dir, exist_ok=True)

        filepath = os.path.join(project_dir, filename)
        with open(filepath, "wb") as f:
            f.write(buffer.getvalue())

        # Create database record
        report = Report(
            project_id=project_id,
            tipo=tipo,
            periodo=periodo,
            formato_financiador=project.financiador.value,
            nombre_archivo=filename,
            ruta=filepath,
            generado_por=generado_por,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        return report

    def generate_pack(
        self,
        project_id: int,
        tipos: list[TipoInforme] | None = None,
        generado_por: str | None = None,
    ) -> Report:
        """Generate a ZIP pack with multiple reports."""
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError("Proyecto no encontrado")

        # Generate the ZIP file
        buffer, filename = self.excel_generator.generate_pack(project, tipos)

        # Save to disk
        project_dir = os.path.join(EXPORTS_DIR, str(project_id))
        os.makedirs(project_dir, exist_ok=True)

        filepath = os.path.join(project_dir, filename)
        with open(filepath, "wb") as f:
            f.write(buffer.getvalue())

        # Create database record (using ficha_proyecto as placeholder type for pack)
        report = Report(
            project_id=project_id,
            tipo=TipoInforme.ficha_proyecto,  # Pack type
            periodo=None,
            formato_financiador=project.financiador.value,
            nombre_archivo=filename,
            ruta=filepath,
            generado_por=generado_por,
            notas="Pack de justificacion (ZIP)",
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        return report

    def get_available_report_types(self, project_id: int) -> list[dict]:
        """Get available report types with their Spanish names."""
        return [
            {"tipo": tipo, "nombre": nombre}
            for tipo, nombre in TIPO_INFORME_NOMBRES.items()
        ]
