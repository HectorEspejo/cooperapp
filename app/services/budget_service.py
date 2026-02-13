from decimal import Decimal
from collections import defaultdict
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload
from app.models.budget import Funder, BudgetLineTemplate, ProjectBudgetLine, CategoriaPartida
from app.models.project import Project, Financiador
from app.schemas.budget import (
    ProjectBudgetLineUpdate,
    ProjectBudgetLineResponse,
    BudgetSummary,
    BudgetTotals,
    CategorySubtotal,
    BudgetValidationAlert,
)


# Mapping from Financiador enum to Funder code
FINANCIADOR_TO_FUNDER_CODE = {
    Financiador.aacid: "AACID",
    Financiador.aecid: "AECID",
    Financiador.diputacion_malaga: "DIPU",
    Financiador.ayuntamiento_malaga: "AYTO",
}


AACID_BUDGET_TEMPLATES = [
    {"code": "A.I.1", "name": "Identificacion y formulacion", "category": CategoriaPartida.servicios, "is_spain_only": False, "order": 1},
    {"code": "A.I.2", "name": "Evaluacion externa", "category": CategoriaPartida.servicios, "is_spain_only": False, "order": 2},
    {"code": "A.I.3", "name": "Auditoria externa", "category": CategoriaPartida.servicios, "is_spain_only": False, "order": 3},
    {"code": "A.I.4", "name": "Otros servicios tecnicos", "category": CategoriaPartida.servicios, "is_spain_only": False, "order": 4},
    {"code": "A.I.5", "name": "Arrendamientos", "category": CategoriaPartida.gastos_directos, "is_spain_only": False, "order": 5},
    {"code": "A.I.6", "name": "Materiales y suministros", "category": CategoriaPartida.gastos_directos, "is_spain_only": False, "order": 6},
    {"code": "A.I.7", "name": "Gastos de funcionamiento", "category": CategoriaPartida.gastos_directos, "is_spain_only": False, "order": 7},
    {"code": "A.I.8", "name": "Viajes y dietas", "category": CategoriaPartida.gastos_directos, "is_spain_only": True, "order": 8},
    {"code": "A.I.9.a", "name": "Personal local", "category": CategoriaPartida.personal, "is_spain_only": False, "order": 9},
    {"code": "A.I.9.b", "name": "Personal expatriado", "category": CategoriaPartida.personal, "is_spain_only": True, "order": 10},
    {"code": "A.I.9.c", "name": "Personal sede", "category": CategoriaPartida.personal, "is_spain_only": True, "order": 11},
    {"code": "A.I.10", "name": "Voluntariado", "category": CategoriaPartida.personal, "is_spain_only": False, "order": 12},
    {"code": "A.I.11", "name": "Testimonio", "category": CategoriaPartida.gastos_directos, "is_spain_only": False, "order": 13},
    {"code": "A.I.12", "name": "Sensibilizacion", "category": CategoriaPartida.gastos_directos, "is_spain_only": False, "order": 14},
    {"code": "A.I.13", "name": "Gastos bancarios", "category": CategoriaPartida.gastos_directos, "is_spain_only": False, "order": 15},
    {"code": "A.I.14", "name": "Fondo rotatorio", "category": CategoriaPartida.gastos_directos, "is_spain_only": False, "order": 16},
    {"code": "A.II.1", "name": "Terrenos", "category": CategoriaPartida.inversiones, "is_spain_only": False, "order": 17},
    {"code": "A.II.2", "name": "Obras", "category": CategoriaPartida.inversiones, "is_spain_only": False, "order": 18},
    {"code": "A.II.3", "name": "Equipos", "category": CategoriaPartida.inversiones, "is_spain_only": False, "order": 19},
    {"code": "B", "name": "Costes indirectos", "category": CategoriaPartida.indirectos, "is_spain_only": True, "order": 20},
]

# AECID uses "AI.X" nomenclature (without intermediate dot)
AECID_BUDGET_TEMPLATES = [
    {"code": "AI.1", "name": "Personal local", "category": CategoriaPartida.personal, "is_spain_only": False, "order": 1},
    {"code": "AI.2", "name": "Personal expatriado", "category": CategoriaPartida.personal, "is_spain_only": True, "order": 2},
    {"code": "AI.3", "name": "Personal voluntario", "category": CategoriaPartida.personal, "is_spain_only": True, "order": 3},
    {"code": "AI.4", "name": "Personal en sede en Espana", "category": CategoriaPartida.personal, "is_spain_only": True, "order": 4},
    {"code": "AI.5", "name": "Viajes, alojamientos y dietas", "category": CategoriaPartida.gastos_directos, "is_spain_only": True, "order": 5},
    {"code": "AI.6", "name": "Equipos, materiales y suministros", "category": CategoriaPartida.gastos_directos, "is_spain_only": False, "order": 6},
    {"code": "AI.7", "name": "Servicios tecnicos y profesionales", "category": CategoriaPartida.servicios, "is_spain_only": False, "order": 7},
    {"code": "AI.8", "name": "Funcionamiento", "category": CategoriaPartida.gastos_directos, "is_spain_only": False, "order": 8},
    {"code": "AI.9", "name": "Auditorias", "category": CategoriaPartida.servicios, "is_spain_only": True, "order": 9},
    {"code": "AI.10", "name": "Evaluaciones", "category": CategoriaPartida.servicios, "is_spain_only": True, "order": 10},
    {"code": "AI.11", "name": "Otros gastos directos", "category": CategoriaPartida.gastos_directos, "is_spain_only": False, "order": 11},
    {"code": "B", "name": "Costes indirectos", "category": CategoriaPartida.indirectos, "is_spain_only": True, "order": 12},
]

# Diputación de Málaga uses simple numbering (1, 2, 3...)
DIPU_BUDGET_TEMPLATES = [
    {"code": "1", "name": "Personal local", "category": CategoriaPartida.personal, "is_spain_only": False, "order": 1},
    {"code": "2", "name": "Personal expatriado", "category": CategoriaPartida.personal, "is_spain_only": True, "order": 2},
    {"code": "3", "name": "Personal en sede", "category": CategoriaPartida.personal, "is_spain_only": True, "order": 3},
    {"code": "4", "name": "Dietas y desplazamientos", "category": CategoriaPartida.gastos_directos, "is_spain_only": True, "order": 4},
    {"code": "5", "name": "Equipamientos y suministros", "category": CategoriaPartida.gastos_directos, "is_spain_only": False, "order": 5},
    {"code": "6", "name": "Ejecucion tecnica (obras, servicios)", "category": CategoriaPartida.servicios, "is_spain_only": False, "order": 6},
    {"code": "7", "name": "Funcionamiento y mantenimiento", "category": CategoriaPartida.gastos_directos, "is_spain_only": False, "order": 7},
    {"code": "8", "name": "Auditoria y evaluacion", "category": CategoriaPartida.servicios, "is_spain_only": True, "order": 8},
    {"code": "9", "name": "Gastos administrativos/indirectos", "category": CategoriaPartida.indirectos, "is_spain_only": True, "order": 9},
]

# Ayuntamiento de Málaga - most simplified structure
AYTO_BUDGET_TEMPLATES = [
    {"code": "1", "name": "Gastos de personal", "category": CategoriaPartida.personal, "is_spain_only": False, "order": 1},
    {"code": "2", "name": "Gastos corrientes", "category": CategoriaPartida.gastos_directos, "is_spain_only": False, "order": 2},
    {"code": "3", "name": "Gastos de inversion", "category": CategoriaPartida.inversiones, "is_spain_only": False, "order": 3},
    {"code": "4", "name": "Gastos de viaje y desplazamiento", "category": CategoriaPartida.gastos_directos, "is_spain_only": True, "order": 4},
    {"code": "5", "name": "Gastos de auditoria/evaluacion", "category": CategoriaPartida.servicios, "is_spain_only": True, "order": 5},
    {"code": "6", "name": "Costes indirectos", "category": CategoriaPartida.indirectos, "is_spain_only": True, "order": 6},
]

# Category display names in Spanish
CATEGORY_NAMES = {
    CategoriaPartida.servicios: "Servicios",
    CategoriaPartida.personal: "Personal",
    CategoriaPartida.gastos_directos: "Gastos Directos",
    CategoriaPartida.inversiones: "Inversiones",
    CategoriaPartida.indirectos: "Costes Indirectos",
}

FUNDERS_DATA = [
    {
        "code": "AACID",
        "name": "Agencia Andaluza de Cooperacion Internacional para el Desarrollo",
        "max_indirect_percentage": None,
        "max_personnel_percentage": None,
        "min_amount_for_audit": None,
    },
    {
        "code": "AECID",
        "name": "Agencia Espanola de Cooperacion Internacional para el Desarrollo",
        "max_indirect_percentage": Decimal("10.00"),
        "max_personnel_percentage": None,
        "min_amount_for_audit": None,
    },
    {
        "code": "DIPU",
        "name": "Diputacion Provincial de Malaga",
        "max_indirect_percentage": Decimal("8.00"),
        "max_personnel_percentage": None,
        "min_amount_for_audit": None,
    },
    {
        "code": "AYTO",
        "name": "Ayuntamiento de Malaga",
        "max_indirect_percentage": Decimal("7.00"),
        "max_personnel_percentage": Decimal("50.00"),
        "min_amount_for_audit": Decimal("30000.00"),
    },
]


class BudgetService:
    def __init__(self, db: Session):
        self.db = db

    # Funder methods
    def get_all_funders(self) -> list[Funder]:
        query = select(Funder).order_by(Funder.name)
        return list(self.db.execute(query).scalars().all())

    def get_funder_by_id(self, funder_id: int) -> Funder | None:
        return self.db.get(Funder, funder_id)

    def get_funder_by_code(self, code: str) -> Funder | None:
        query = select(Funder).where(Funder.code == code)
        return self.db.execute(query).scalar_one_or_none()

    def get_funder_for_financiador(self, financiador: Financiador) -> Funder | None:
        """Get the Funder that corresponds to a project's Financiador enum"""
        code = FINANCIADOR_TO_FUNDER_CODE.get(financiador)
        if code:
            return self.get_funder_by_code(code)
        return None

    # Template methods
    def get_funder_templates(self, funder_id: int) -> list[BudgetLineTemplate]:
        query = (
            select(BudgetLineTemplate)
            .where(BudgetLineTemplate.funder_id == funder_id)
            .order_by(BudgetLineTemplate.order)
        )
        return list(self.db.execute(query).scalars().all())

    # Project budget methods
    def get_project_budget(self, project_id: int) -> list[ProjectBudgetLine]:
        query = (
            select(ProjectBudgetLine)
            .where(ProjectBudgetLine.project_id == project_id)
            .order_by(ProjectBudgetLine.order)
        )
        return list(self.db.execute(query).scalars().all())

    def get_project_budget_summary(self, project_id: int) -> BudgetSummary:
        project = self.db.get(Project, project_id)
        lines = self.get_project_budget(project_id)

        funder = None
        if project and project.funder_id:
            funder = self.get_funder_by_id(project.funder_id)

        # Calculate totals for direct costs (everything except indirectos)
        direct_lines = [line for line in lines if line.category != CategoriaPartida.indirectos]
        indirect_lines = [line for line in lines if line.category == CategoriaPartida.indirectos]
        personnel_lines = [line for line in lines if line.category == CategoriaPartida.personal]

        total_direct_aprobado = sum(line.aprobado for line in direct_lines)
        total_aprobado = sum(line.aprobado for line in lines)
        total_personnel_aprobado = sum(line.aprobado for line in personnel_lines)
        total_ejecutado_espana = sum(line.ejecutado_espana for line in lines)
        total_ejecutado_terreno = sum(line.ejecutado_terreno for line in lines)
        total_ejecutado = total_ejecutado_espana + total_ejecutado_terreno
        total_diferencia = total_aprobado - total_ejecutado

        porcentaje_global = 0.0
        if total_aprobado > 0:
            porcentaje_global = float((total_ejecutado / total_aprobado) * 100)

        # Calculate validation alerts
        validation_alerts = []

        # Get funder's limits for validation
        funder_max_indirect = funder.max_indirect_percentage if funder else None
        funder_max_personnel = funder.max_personnel_percentage if funder else None
        funder_min_audit = funder.min_amount_for_audit if funder else None

        # Check if audit is required based on project subvencion
        project_subvencion = project.subvencion if project else None
        audit_required = True
        if funder_min_audit is not None and project_subvencion is not None:
            audit_required = project_subvencion >= funder_min_audit

        # Check if total approved exceeds subvencion
        if project_subvencion is not None and total_aprobado > project_subvencion:
            exceso = total_aprobado - project_subvencion
            validation_alerts.append(BudgetValidationAlert(
                line_id=None,
                line_code=None,
                message=f"El total aprobado ({total_aprobado:,.2f} EUR) supera la subvencion "
                        f"({project_subvencion:,.2f} EUR) en {exceso:,.2f} EUR",
                alert_type="error",
            ))

        # Check personnel percentage validation (AYTO: max 50%)
        if funder_max_personnel is not None and total_aprobado > 0:
            personnel_percentage = (total_personnel_aprobado / total_aprobado) * Decimal("100")
            if personnel_percentage > funder_max_personnel:
                validation_alerts.append(BudgetValidationAlert(
                    line_id=None,
                    line_code=None,
                    message=f"Los gastos de personal ({personnel_percentage:.1f}%) superan el {funder_max_personnel}% "
                            f"permitido del total del proyecto. Maximo: {total_aprobado * funder_max_personnel / Decimal('100'):,.2f} EUR, "
                            f"Actual: {total_personnel_aprobado:,.2f} EUR",
                    alert_type="error",
                ))

        # Convert lines to response models and check for max_percentage alerts
        lines_response = []
        for line in lines:
            has_max_percentage_alert = False
            is_optional = False

            # Check max_percentage validation for indirect costs using funder's limit
            if line.category == CategoriaPartida.indirectos and funder_max_indirect is not None and total_direct_aprobado > 0:
                max_allowed = total_direct_aprobado * funder_max_indirect / Decimal("100")
                if line.aprobado > max_allowed:
                    has_max_percentage_alert = True
                    validation_alerts.append(BudgetValidationAlert(
                        line_id=line.id,
                        line_code=line.code,
                        message=f"La partida {line.code} ({line.name}) supera el {funder_max_indirect}% permitido. "
                                f"Maximo: {max_allowed:,.2f} EUR, Actual: {line.aprobado:,.2f} EUR",
                        alert_type="error",
                    ))

            # Mark audit line as optional if below threshold
            if line.category == CategoriaPartida.servicios and "audit" in line.name.lower() and not audit_required:
                is_optional = True

            lines_response.append(ProjectBudgetLineResponse(
                id=line.id,
                project_id=line.project_id,
                template_id=line.template_id,
                parent_id=line.parent_id,
                code=line.code,
                name=line.name,
                category=line.category,
                is_spain_only=line.is_spain_only,
                order=line.order,
                max_percentage=line.max_percentage,
                aprobado=line.aprobado,
                ejecutado_espana=line.ejecutado_espana,
                ejecutado_terreno=line.ejecutado_terreno,
                total_ejecutado=line.total_ejecutado,
                diferencia=line.diferencia,
                porcentaje_ejecucion=line.porcentaje_ejecucion,
                has_deviation_alert=line.has_deviation_alert,
                has_max_percentage_alert=has_max_percentage_alert,
                is_optional=is_optional,
                created_at=line.created_at,
                updated_at=line.updated_at,
            ))

        # Calculate category subtotals
        category_subtotals = self._calculate_category_subtotals(lines_response)

        return BudgetSummary(
            project_id=project_id,
            project_subvencion=project_subvencion,
            funder_id=funder.id if funder else None,
            funder_code=funder.code if funder else None,
            funder_name=funder.name if funder else None,
            funder_max_indirect_percentage=funder.max_indirect_percentage if funder else None,
            funder_max_personnel_percentage=funder.max_personnel_percentage if funder else None,
            funder_min_amount_for_audit=funder.min_amount_for_audit if funder else None,
            audit_required=audit_required,
            lines=lines_response,
            category_subtotals=category_subtotals,
            totals=BudgetTotals(
                total_aprobado=total_aprobado,
                total_ejecutado_espana=total_ejecutado_espana,
                total_ejecutado_terreno=total_ejecutado_terreno,
                total_ejecutado=total_ejecutado,
                total_diferencia=total_diferencia,
                porcentaje_ejecucion_global=porcentaje_global,
            ),
            has_budget=len(lines) > 0,
            validation_alerts=validation_alerts,
        )

    def _calculate_category_subtotals(self, lines: list[ProjectBudgetLineResponse]) -> list[CategorySubtotal]:
        """Calculate subtotals grouped by category"""
        # Group lines by category
        category_lines = defaultdict(list)
        for line in lines:
            category_lines[line.category].append(line)

        # Calculate subtotals for each category
        subtotals = []
        # Define category order
        category_order = [
            CategoriaPartida.personal,
            CategoriaPartida.servicios,
            CategoriaPartida.gastos_directos,
            CategoriaPartida.inversiones,
            CategoriaPartida.indirectos,
        ]

        for category in category_order:
            cat_lines = category_lines.get(category, [])
            if not cat_lines:
                continue

            total_aprobado = sum(line.aprobado for line in cat_lines)
            total_ejecutado_espana = sum(line.ejecutado_espana for line in cat_lines)
            total_ejecutado_terreno = sum(line.ejecutado_terreno for line in cat_lines)
            total_ejecutado = total_ejecutado_espana + total_ejecutado_terreno
            total_diferencia = total_aprobado - total_ejecutado

            porcentaje = 0.0
            if total_aprobado > 0:
                porcentaje = float((total_ejecutado / total_aprobado) * 100)

            subtotals.append(CategorySubtotal(
                category=category,
                category_name=CATEGORY_NAMES.get(category, category.value),
                total_aprobado=total_aprobado,
                total_ejecutado_espana=total_ejecutado_espana,
                total_ejecutado_terreno=total_ejecutado_terreno,
                total_ejecutado=total_ejecutado,
                total_diferencia=total_diferencia,
                porcentaje_ejecucion=porcentaje,
                lines=cat_lines,
            ))

        return subtotals

    def initialize_project_budget(
        self, project_id: int, funder_id: int
    ) -> list[ProjectBudgetLine]:
        # Check if budget already exists
        existing = self.get_project_budget(project_id)
        if existing:
            return existing

        # Get project and update funder_id
        project = self.db.get(Project, project_id)
        if project:
            project.funder_id = funder_id

        # Get templates for the funder
        templates = self.get_funder_templates(funder_id)

        # Create budget lines from templates (first pass: create all lines)
        budget_lines = []
        template_to_line = {}  # Map template_id to budget_line for parent resolution

        for template in templates:
            line = ProjectBudgetLine(
                project_id=project_id,
                template_id=template.id,
                code=template.code,
                name=template.name,
                category=template.category,
                is_spain_only=template.is_spain_only,
                order=template.order,
                max_percentage=template.max_percentage,
                aprobado=Decimal("0"),
                ejecutado_espana=Decimal("0"),
                ejecutado_terreno=Decimal("0"),
            )
            self.db.add(line)
            budget_lines.append(line)
            template_to_line[template.id] = line

        # Flush to get IDs
        self.db.flush()

        # Second pass: resolve parent relationships
        for template in templates:
            if template.parent_id and template.parent_id in template_to_line:
                line = template_to_line[template.id]
                parent_line = template_to_line[template.parent_id]
                line.parent_id = parent_line.id

        self.db.commit()
        for line in budget_lines:
            self.db.refresh(line)

        return budget_lines

    def initialize_budget_from_project(self, project: Project) -> list[ProjectBudgetLine]:
        """Initialize budget for a project based on its financiador field"""
        # Check if budget already exists
        existing = self.get_project_budget(project.id)
        if existing:
            return existing

        # Get funder from project's financiador
        funder = self.get_funder_for_financiador(project.financiador)
        if not funder:
            return []

        # Get templates for the funder
        templates = self.get_funder_templates(funder.id)
        if not templates:
            return []

        # Update project's funder_id
        project.funder_id = funder.id

        # Create budget lines from templates
        budget_lines = []
        template_to_line = {}

        for template in templates:
            line = ProjectBudgetLine(
                project_id=project.id,
                template_id=template.id,
                code=template.code,
                name=template.name,
                category=template.category,
                is_spain_only=template.is_spain_only,
                order=template.order,
                max_percentage=template.max_percentage,
                aprobado=Decimal("0"),
                ejecutado_espana=Decimal("0"),
                ejecutado_terreno=Decimal("0"),
            )
            self.db.add(line)
            budget_lines.append(line)
            template_to_line[template.id] = line

        # Flush to get IDs
        self.db.flush()

        # Resolve parent relationships
        for template in templates:
            if template.parent_id and template.parent_id in template_to_line:
                line = template_to_line[template.id]
                parent_line = template_to_line[template.parent_id]
                line.parent_id = parent_line.id

        self.db.commit()
        for line in budget_lines:
            self.db.refresh(line)

        return budget_lines

    def reinitialize_budget_for_new_funder(self, project: Project) -> list[ProjectBudgetLine]:
        """Delete existing budget and create new one based on project's financiador"""
        # Get the new funder
        new_funder = self.get_funder_for_financiador(project.financiador)
        if not new_funder:
            return []

        # Check if funder changed
        if project.funder_id == new_funder.id:
            # Same funder, return existing budget
            return self.get_project_budget(project.id)

        # Delete existing budget lines
        existing = self.get_project_budget(project.id)
        for line in existing:
            self.db.delete(line)

        # Update project's funder_id
        project.funder_id = new_funder.id

        # Get templates for the new funder
        templates = self.get_funder_templates(new_funder.id)
        if not templates:
            self.db.commit()
            return []

        # Create new budget lines
        budget_lines = []
        template_to_line = {}

        for template in templates:
            line = ProjectBudgetLine(
                project_id=project.id,
                template_id=template.id,
                code=template.code,
                name=template.name,
                category=template.category,
                is_spain_only=template.is_spain_only,
                order=template.order,
                max_percentage=template.max_percentage,
                aprobado=Decimal("0"),
                ejecutado_espana=Decimal("0"),
                ejecutado_terreno=Decimal("0"),
            )
            self.db.add(line)
            budget_lines.append(line)
            template_to_line[template.id] = line

        # Flush to get IDs
        self.db.flush()

        # Resolve parent relationships
        for template in templates:
            if template.parent_id and template.parent_id in template_to_line:
                line = template_to_line[template.id]
                parent_line = template_to_line[template.parent_id]
                line.parent_id = parent_line.id

        self.db.commit()
        for line in budget_lines:
            self.db.refresh(line)

        return budget_lines

    def get_budget_line_by_id(self, line_id: int) -> ProjectBudgetLine | None:
        return self.db.get(ProjectBudgetLine, line_id)

    def update_budget_line(
        self, line_id: int, data: ProjectBudgetLineUpdate
    ) -> ProjectBudgetLine | None:
        line = self.get_budget_line_by_id(line_id)
        if not line:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(line, field, value)

        self.db.commit()
        self.db.refresh(line)
        return line

    # Seeding methods
    def seed_funders(self):
        """Seed funders data if not exists"""
        existing = self.db.execute(select(func.count(Funder.id))).scalar()
        if existing == 0:
            for funder_data in FUNDERS_DATA:
                funder = Funder(**funder_data)
                self.db.add(funder)
            self.db.commit()

    def seed_aacid_templates(self):
        """Seed AACID budget templates if not exists"""
        aacid = self.get_funder_by_code("AACID")
        if not aacid:
            return

        existing = self.db.execute(
            select(func.count(BudgetLineTemplate.id))
            .where(BudgetLineTemplate.funder_id == aacid.id)
        ).scalar()

        if existing == 0:
            for template_data in AACID_BUDGET_TEMPLATES:
                template = BudgetLineTemplate(funder_id=aacid.id, **template_data)
                self.db.add(template)
            self.db.commit()

    def seed_aecid_templates(self):
        """Seed AECID budget templates if not exists"""
        aecid = self.get_funder_by_code("AECID")
        if not aecid:
            return

        existing = self.db.execute(
            select(func.count(BudgetLineTemplate.id))
            .where(BudgetLineTemplate.funder_id == aecid.id)
        ).scalar()

        if existing == 0:
            for template_data in AECID_BUDGET_TEMPLATES:
                template = BudgetLineTemplate(funder_id=aecid.id, **template_data)
                self.db.add(template)
            self.db.commit()

    def seed_dipu_templates(self):
        """Seed Diputación de Málaga budget templates if not exists"""
        dipu = self.get_funder_by_code("DIPU")
        if not dipu:
            return

        existing = self.db.execute(
            select(func.count(BudgetLineTemplate.id))
            .where(BudgetLineTemplate.funder_id == dipu.id)
        ).scalar()

        if existing == 0:
            for template_data in DIPU_BUDGET_TEMPLATES:
                template = BudgetLineTemplate(funder_id=dipu.id, **template_data)
                self.db.add(template)
            self.db.commit()

    def seed_ayto_templates(self):
        """Seed Ayuntamiento de Málaga budget templates if not exists"""
        ayto = self.get_funder_by_code("AYTO")
        if not ayto:
            return

        existing = self.db.execute(
            select(func.count(BudgetLineTemplate.id))
            .where(BudgetLineTemplate.funder_id == ayto.id)
        ).scalar()

        if existing == 0:
            for template_data in AYTO_BUDGET_TEMPLATES:
                template = BudgetLineTemplate(funder_id=ayto.id, **template_data)
                self.db.add(template)
            self.db.commit()
