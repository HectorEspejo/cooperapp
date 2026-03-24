import io
import os
from datetime import datetime

from pypdf import PdfReader, PdfWriter
from pypdf.generic import TextStringObject, NameObject, BooleanObject
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.logical_framework import LogicalFramework, SpecificObjective, Result, Activity, Indicator
from app.models.aacid import (
    ProjectNarrative, ProjectBeneficiary, ProjectVolunteer, ProjectMarker,
    NARRATIVE_SECTIONS, MARKER_NAMES,
)
from app.models.report import Report, TipoInforme
from app.services.aacid_field_map import FIELD_MAP, NARRATIVE_SECTIONS as FIELD_NARRATIVE_SECTIONS, REQUIRED_NARRATIVE_SECTIONS


EXPORTS_DIR = "exports"
PDF_TEMPLATE_PATH = os.path.join("docs", "other", "anexo-aacid.pdf")


class AACIDFormService:
    def __init__(self, db: Session):
        self.db = db

    # ---- Campos AACID del proyecto ----

    def get_project_aacid_fields(self, project_id: int) -> dict:
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError("Proyecto no encontrado")
        return {
            "convocatoria": project.convocatoria,
            "numero_aacid": project.numero_aacid,
            "municipios": project.municipios,
            "duracion_meses": project.duracion_meses,
            "descripcion_breve": project.descripcion_breve,
            "crs_sector_1": project.crs_sector_1,
            "crs_sector_2": project.crs_sector_2,
            "crs_sector_3": project.crs_sector_3,
            "ods_meta_1": project.ods_meta_1,
            "ods_meta_2": project.ods_meta_2,
            "ods_meta_3": project.ods_meta_3,
        }

    def update_project_aacid_fields(self, project_id: int, data: dict) -> Project:
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError("Proyecto no encontrado")
        for key, value in data.items():
            if hasattr(project, key):
                setattr(project, key, value)
        self.db.commit()
        self.db.refresh(project)
        return project

    # ---- Narrativas CRUD ----

    def get_narratives(self, project_id: int) -> list[ProjectNarrative]:
        query = (
            select(ProjectNarrative)
            .where(ProjectNarrative.project_id == project_id)
            .order_by(ProjectNarrative.section_code)
        )
        return list(self.db.execute(query).scalars().all())

    def get_narratives_dict(self, project_id: int) -> dict[str, str]:
        """Returns dict of {section_code: content}"""
        narratives = self.get_narratives(project_id)
        return {n.section_code: n.content for n in narratives}

    def upsert_narrative(self, project_id: int, section_code: str, content: str) -> ProjectNarrative:
        # Verify project exists
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError("Proyecto no encontrado")

        # Find existing or create new
        query = select(ProjectNarrative).where(
            ProjectNarrative.project_id == project_id,
            ProjectNarrative.section_code == section_code,
        )
        narrative = self.db.execute(query).scalar_one_or_none()

        if narrative:
            narrative.content = content
            narrative.updated_at = datetime.utcnow()
        else:
            max_chars = 1000 if section_code == "1.7" else 4000
            narrative = ProjectNarrative(
                project_id=project_id,
                section_code=section_code,
                content=content,
                max_chars=max_chars,
            )
            self.db.add(narrative)

        self.db.commit()
        self.db.refresh(narrative)
        return narrative

    # ---- Beneficiarios CRUD ----

    def get_beneficiaries(self, project_id: int) -> ProjectBeneficiary | None:
        query = select(ProjectBeneficiary).where(
            ProjectBeneficiary.project_id == project_id
        )
        return self.db.execute(query).scalar_one_or_none()

    def upsert_beneficiaries(self, project_id: int, data: dict) -> ProjectBeneficiary:
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError("Proyecto no encontrado")

        beneficiary = self.get_beneficiaries(project_id)
        if beneficiary:
            for key, value in data.items():
                if hasattr(beneficiary, key):
                    setattr(beneficiary, key, value)
        else:
            beneficiary = ProjectBeneficiary(project_id=project_id, **data)
            self.db.add(beneficiary)

        self.db.commit()
        self.db.refresh(beneficiary)
        return beneficiary

    # ---- Voluntarios CRUD ----

    def get_volunteers(self, project_id: int) -> ProjectVolunteer | None:
        query = select(ProjectVolunteer).where(
            ProjectVolunteer.project_id == project_id
        )
        return self.db.execute(query).scalar_one_or_none()

    def upsert_volunteers(self, project_id: int, data: dict) -> ProjectVolunteer:
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError("Proyecto no encontrado")

        volunteer = self.get_volunteers(project_id)
        if volunteer:
            for key, value in data.items():
                if hasattr(volunteer, key):
                    setattr(volunteer, key, value)
        else:
            volunteer = ProjectVolunteer(project_id=project_id, **data)
            self.db.add(volunteer)

        self.db.commit()
        self.db.refresh(volunteer)
        return volunteer

    # ---- Marcadores CRUD ----

    def get_markers(self, project_id: int) -> list[ProjectMarker]:
        query = (
            select(ProjectMarker)
            .where(ProjectMarker.project_id == project_id)
            .order_by(ProjectMarker.marker_name)
        )
        return list(self.db.execute(query).scalars().all())

    def upsert_marker(self, project_id: int, marker_name: str, level: str) -> ProjectMarker:
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError("Proyecto no encontrado")

        query = select(ProjectMarker).where(
            ProjectMarker.project_id == project_id,
            ProjectMarker.marker_name == marker_name,
        )
        marker = self.db.execute(query).scalar_one_or_none()

        if marker:
            marker.level = level
        else:
            marker = ProjectMarker(
                project_id=project_id,
                marker_name=marker_name,
                level=level,
            )
            self.db.add(marker)

        self.db.commit()
        self.db.refresh(marker)
        return marker

    # ---- Validacion ----

    def validate(self, project_id: int) -> dict:
        """Validates project data for PDF generation. Returns dict with valid, errors, warnings."""
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError("Proyecto no encontrado")

        errors = []
        warnings = []
        narratives = self.get_narratives_dict(project_id)

        # Check required narrative sections
        for code in REQUIRED_NARRATIVE_SECTIONS:
            if not narratives.get(code, "").strip():
                errors.append({
                    "field": code,
                    "label": FIELD_NARRATIVE_SECTIONS.get(code, code),
                    "message": "Campo obligatorio vacio",
                })

        # Check character limits on narratives
        for code, content in narratives.items():
            max_chars = 4000
            if len(content) > max_chars:
                warnings.append({
                    "field": code,
                    "label": FIELD_NARRATIVE_SECTIONS.get(code, code),
                    "current": len(content),
                    "max": max_chars,
                    "excess": len(content) - max_chars,
                })

        # Check descripcion_breve
        if project.descripcion_breve and len(project.descripcion_breve) > 1000:
            warnings.append({
                "field": "1.7",
                "label": "Descripcion breve",
                "current": len(project.descripcion_breve),
                "max": 1000,
                "excess": len(project.descripcion_breve) - 1000,
            })

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    # ---- Vista previa ----

    def get_preview(self, project_id: int) -> dict:
        """Returns preview with validation and section status."""
        validation = self.validate(project_id)
        narratives = self.get_narratives_dict(project_id)
        project = self.db.get(Project, project_id)

        sections = []

        # Add descripcion_breve as section 1.7
        desc = project.descripcion_breve or ""
        sections.append({
            "code": "1.7",
            "label": "Descripcion breve del proyecto",
            "chars": len(desc),
            "max_chars": 1000,
            "filled": bool(desc.strip()),
            "exceeds": len(desc) > 1000,
            "excess": max(0, len(desc) - 1000),
        })

        # Add all narrative sections
        for code, label in FIELD_NARRATIVE_SECTIONS.items():
            content = narratives.get(code, "")
            max_chars = 4000
            sections.append({
                "code": code,
                "label": label,
                "chars": len(content),
                "max_chars": max_chars,
                "filled": bool(content.strip()),
                "exceeds": len(content) > max_chars,
                "excess": max(0, len(content) - max_chars),
            })

        return {
            "validation": validation,
            "sections": sections,
        }

    # ---- Generacion PDF ----

    def generate_pdf(self, project_id: int, generado_por: str | None = None) -> Report:
        """Generates the filled Anexo II A PDF and saves it as a Report."""
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError("Proyecto no encontrado")

        # Build field values
        values = self._build_field_values(project)

        # Read template and fill
        reader = PdfReader(PDF_TEMPLATE_PATH)
        writer = PdfWriter()
        writer.append(reader)

        # Set NeedAppearances flag
        if "/AcroForm" in writer._root_object:
            writer._root_object["/AcroForm"][
                NameObject("/NeedAppearances")] = BooleanObject(True)

        # Fill fields by walking annotations
        for page in writer.pages:
            annots = page.get("/Annots")
            if not annots:
                continue
            for annot_ref in annots:
                annot = annot_ref.get_object()
                full_name = self._get_full_field_name(annot)

                for pattern, value in values.items():
                    if pattern in full_name and value:
                        annot[NameObject("/V")] = TextStringObject(str(value))
                        if "/AP" in annot:
                            del annot["/AP"]
                        break

        # Write to bytes
        buffer = io.BytesIO()
        writer.write(buffer)
        pdf_bytes = buffer.getvalue()

        # Save to disk
        project_dir = os.path.join(EXPORTS_DIR, str(project_id))
        os.makedirs(project_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Anexo_IIA_{project.codigo_contable}_{timestamp}.pdf"
        filepath = os.path.join(project_dir, filename)

        with open(filepath, "wb") as f:
            f.write(pdf_bytes)

        # Create Report record
        report = Report(
            project_id=project_id,
            tipo=TipoInforme.anexo_iia,
            formato_financiador="AACID",
            nombre_archivo=filename,
            ruta=filepath,
            generado_por=generado_por,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        return report

    def _get_full_field_name(self, annot) -> str:
        """Reconstructs the full field name by walking up /Parent chain."""
        name = str(annot.get("/T", ""))
        obj = annot
        while "/Parent" in obj:
            parent = obj["/Parent"].get_object()
            parent_name = str(parent.get("/T", ""))
            if parent_name:
                name = parent_name + "." + name
            obj = parent
        return name

    def _build_field_values(self, project: Project) -> dict[str, str]:
        """Builds the {pdf_pattern: value} dict from DB data."""
        narratives = self.get_narratives_dict(project.id)
        beneficiaries = self.get_beneficiaries(project.id)
        volunteers = self.get_volunteers(project.id)

        values = {}

        for pdf_pattern, config in FIELD_MAP.items():
            source = config["source"]

            if source.startswith("narrative:"):
                code = source.split(":")[1]
                values[pdf_pattern] = narratives.get(code, "")
            elif source.startswith("project."):
                attr = source.split(".")[1]
                val = getattr(project, attr, None)
                if val is not None:
                    if hasattr(val, "strftime"):  # date/datetime
                        values[pdf_pattern] = val.strftime("%d/%m/%Y")
                    else:
                        values[pdf_pattern] = str(val)
                else:
                    values[pdf_pattern] = ""
            elif source.startswith("beneficiaries."):
                attr = source.split(".")[1]
                if beneficiaries:
                    val = getattr(beneficiaries, attr, 0)
                    values[pdf_pattern] = str(val) if val else ""
                else:
                    values[pdf_pattern] = ""
            elif source.startswith("volunteers."):
                attr = source.split(".")[1]
                if volunteers:
                    val = getattr(volunteers, attr, 0)
                    values[pdf_pattern] = str(val) if val else ""
                else:
                    values[pdf_pattern] = ""

        # Add matrix values (results, activities from logical framework)
        self._add_matrix_values(project, values)

        # Add indicator values
        self._add_indicator_values(project, values)

        return values

    def _add_matrix_values(self, project: Project, values: dict):
        """Injects results and activities into the planning matrix."""
        fw = project.logical_framework
        if not fw:
            return

        # Objetivo general
        values["CAJA-2\\.3\\.1[0].LINEA[1].NOMBRE-APELLIDOS-RAZ\xd3N[0]"] = fw.objetivo_general or ""

        # Objetivo especifico (first one)
        if fw.specific_objectives:
            oe = fw.specific_objectives[0]
            values["CAJA-2\\.3\\.1[0].LINEA[2].NOMBRE-APELLIDOS-RAZ\xd3N[0]"] = oe.descripcion or ""

            # Get all results across specific objectives
            all_results = []
            for so in fw.specific_objectives:
                all_results.extend(so.results)

            # R1 -> CAJA-R-1[0], R2 -> CAJA-R-2[0], R3 -> CAJA-R-2[1]
            for r_idx, result in enumerate(all_results[:3]):
                if r_idx == 0:
                    prefix = "CAJA-R-1[0]"
                elif r_idx == 1:
                    prefix = "CAJA-R-2[0]"
                else:
                    prefix = "CAJA-R-2[1]"

                values[f"CAJA-2\\.3\\.1[0].CUADRO[0].{prefix}.CAJA-1[0].CAMPO-RELLENABLE[0]"] = result.descripcion or ""

                for a_idx, act in enumerate(result.activities[:10]):
                    values[f"CAJA-2\\.3\\.1[0].CUADRO[0].{prefix}.CAJA-2[0].lin[{a_idx}].RELLENABLE[0]"] = act.numero or ""
                    values[f"CAJA-2\\.3\\.1[0].CUADRO[0].{prefix}.CAJA-3[0].lin[{a_idx}].RELLENABLE[0]"] = act.descripcion or ""

    def _add_indicator_values(self, project: Project, values: dict):
        """Injects indicator values into the indicator tables."""
        fw = project.logical_framework
        if not fw:
            return

        # 2.3.2[0] = Indicadores de objetivo especifico (up to 3 rows, 4 cols each)
        if fw.specific_objectives:
            oe = fw.specific_objectives[0]
            for i_idx, ind in enumerate(oe.indicators[:3]):
                row = f"CAJA-2\\.3\\.2[0].LINEA[2].CUERPO[0].LINEA[{i_idx}]"
                values[f"{row}.TEXTO[0]"] = ind.descripcion or ""
                values[f"{row}.TEXTO[1]"] = ind.valor_base or ""
                values[f"{row}.TEXTO[2]"] = ind.valor_meta or ""
                values[f"{row}.TEXTO[3]"] = ind.fuente_verificacion or ""

        # 2.3.2[1] = Indicadores de resultados (up to 15 rows, 5 cols each)
        all_results = []
        if fw.specific_objectives:
            for so in fw.specific_objectives:
                all_results.extend(so.results)

        row_idx = 0
        for result in all_results[:3]:
            for ind in result.indicators:
                if row_idx >= 15:
                    break
                row = f"CAJA-2\\.3\\.2[1].LINEA[2].CUERPO[0].LINEA[{row_idx}]"
                values[f"{row}.TEXTO[0]"] = result.numero or ""
                values[f"{row}.TEXTO[1]"] = ind.descripcion or ""
                values[f"{row}.TEXTO[2]"] = ind.valor_base or ""
                values[f"{row}.TEXTO[3]"] = ind.valor_meta or ""
                values[f"{row}.TEXTO[4]"] = ind.fuente_verificacion or ""
                row_idx += 1
