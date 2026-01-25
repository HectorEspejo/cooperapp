from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from app.models.project import Project, Plazo, ODSObjetivo, EstadoProyecto, TipoProyecto, ODS_NOMBRES, Financiador
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectStats, PlazoCreate, PlazoUpdate


class ProjectService:
    def __init__(self, db: Session):
        self.db = db
        self._budget_service = None

    @property
    def budget_service(self):
        """Lazy load budget service to avoid circular imports"""
        if self._budget_service is None:
            from app.services.budget_service import BudgetService
            self._budget_service = BudgetService(self.db)
        return self._budget_service

    def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        estado: EstadoProyecto | None = None,
        tipo: TipoProyecto | None = None,
        pais: str | None = None,
        search: str | None = None,
    ) -> tuple[list[Project], int]:
        query = select(Project).options(
            selectinload(Project.plazos),
            selectinload(Project.ods_objetivos)
        )

        if estado:
            query = query.where(Project.estado == estado)
        if tipo:
            query = query.where(Project.tipo == tipo)
        if pais:
            query = query.where(Project.pais == pais)
        if search:
            search_term = f"%{search}%"
            query = query.where(
                (Project.titulo.ilike(search_term))
                | (Project.codigo_contable.ilike(search_term))
                | (Project.codigo_area.ilike(search_term))
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = self.db.execute(count_query).scalar() or 0

        # Apply pagination
        query = query.order_by(Project.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        projects = self.db.execute(query).scalars().all()
        return list(projects), total

    def get_by_id(self, project_id: int) -> Project | None:
        query = select(Project).options(
            selectinload(Project.plazos),
            selectinload(Project.ods_objetivos)
        ).where(Project.id == project_id)
        return self.db.execute(query).scalar_one_or_none()

    def get_by_codigo_contable(self, codigo: str) -> Project | None:
        query = select(Project).where(Project.codigo_contable == codigo)
        return self.db.execute(query).scalar_one_or_none()

    def create(self, data: ProjectCreate) -> Project:
        project_data = data.model_dump(exclude={"plazos", "ods_ids"})
        project = Project(**project_data)

        # Add plazos
        for plazo_data in data.plazos:
            plazo = Plazo(**plazo_data.model_dump())
            project.plazos.append(plazo)

        # Add ODS
        if data.ods_ids:
            ods_list = self.db.execute(
                select(ODSObjetivo).where(ODSObjetivo.id.in_(data.ods_ids))
            ).scalars().all()
            project.ods_objetivos = list(ods_list)

        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)

        # Auto-initialize budget based on financiador
        self.budget_service.initialize_budget_from_project(project)

        return project

    def update(self, project_id: int, data: ProjectUpdate) -> Project | None:
        project = self.get_by_id(project_id)
        if not project:
            return None

        # Track if financiador changed
        old_financiador = project.financiador

        update_data = data.model_dump(exclude_unset=True, exclude={"ods_ids"})
        for field, value in update_data.items():
            setattr(project, field, value)

        # Update ODS if provided
        if data.ods_ids is not None:
            ods_list = self.db.execute(
                select(ODSObjetivo).where(ODSObjetivo.id.in_(data.ods_ids))
            ).scalars().all()
            project.ods_objetivos = list(ods_list)

        self.db.commit()
        self.db.refresh(project)

        # If financiador changed, reinitialize budget
        if data.financiador is not None and data.financiador != old_financiador:
            self.budget_service.reinitialize_budget_for_new_funder(project)

        return project

    def delete(self, project_id: int) -> bool:
        project = self.get_by_id(project_id)
        if not project:
            return False

        self.db.delete(project)
        self.db.commit()
        return True

    # Plazo methods
    def add_plazo(self, project_id: int, data: PlazoCreate) -> Plazo | None:
        project = self.get_by_id(project_id)
        if not project:
            return None

        plazo = Plazo(project_id=project_id, **data.model_dump())
        self.db.add(plazo)
        self.db.commit()
        self.db.refresh(plazo)
        return plazo

    def update_plazo(self, plazo_id: int, data: PlazoUpdate) -> Plazo | None:
        plazo = self.db.get(Plazo, plazo_id)
        if not plazo:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(plazo, field, value)

        self.db.commit()
        self.db.refresh(plazo)
        return plazo

    def delete_plazo(self, plazo_id: int) -> bool:
        plazo = self.db.get(Plazo, plazo_id)
        if not plazo:
            return False

        self.db.delete(plazo)
        self.db.commit()
        return True

    def toggle_plazo(self, plazo_id: int) -> Plazo | None:
        plazo = self.db.get(Plazo, plazo_id)
        if not plazo:
            return None

        plazo.completado = not plazo.completado
        self.db.commit()
        self.db.refresh(plazo)
        return plazo

    # ODS methods
    def get_all_ods(self) -> list[ODSObjetivo]:
        query = select(ODSObjetivo).order_by(ODSObjetivo.id)
        return list(self.db.execute(query).scalars().all())

    def seed_ods(self):
        """Seed ODS data if not exists"""
        existing = self.db.execute(select(func.count(ODSObjetivo.id))).scalar()
        if existing == 0:
            for numero, nombre in ODS_NOMBRES.items():
                ods = ODSObjetivo(numero=numero, nombre=nombre)
                self.db.add(ods)
            self.db.commit()

    def get_stats(self) -> ProjectStats:
        # Total projects
        total = self.db.execute(select(func.count(Project.id))).scalar() or 0

        # Total subvencion
        total_subv = self.db.execute(
            select(func.sum(Project.subvencion))
        ).scalar() or Decimal("0")

        # By estado
        estado_query = (
            select(Project.estado, func.count(Project.id))
            .group_by(Project.estado)
        )
        by_estado = {
            row[0].value: row[1]
            for row in self.db.execute(estado_query).all()
        }

        # By tipo
        tipo_query = (
            select(Project.tipo, func.count(Project.id))
            .group_by(Project.tipo)
        )
        by_tipo = {
            row[0].value: row[1]
            for row in self.db.execute(tipo_query).all()
        }

        # By pais (top 10)
        pais_query = (
            select(Project.pais, func.count(Project.id))
            .group_by(Project.pais)
            .order_by(func.count(Project.id).desc())
            .limit(10)
        )
        by_pais = {
            row[0]: row[1]
            for row in self.db.execute(pais_query).all()
        }

        return ProjectStats(
            total_projects=total,
            total_subvencion=total_subv,
            by_estado=by_estado,
            by_tipo=by_tipo,
            by_pais=by_pais,
        )

    def get_unique_paises(self) -> list[str]:
        query = select(Project.pais).distinct().order_by(Project.pais)
        return [row[0] for row in self.db.execute(query).all()]

    def get_unique_sectores(self) -> list[str]:
        query = select(Project.sector).distinct().order_by(Project.sector)
        return [row[0] for row in self.db.execute(query).all()]
