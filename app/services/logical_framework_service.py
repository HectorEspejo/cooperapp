from datetime import date
from decimal import Decimal, InvalidOperation
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload
from app.models.logical_framework import (
    LogicalFramework, SpecificObjective, Result, Activity,
    Indicator, IndicatorUpdate as IndicatorUpdateModel, EstadoActividad
)
from app.schemas.logical_framework import (
    LogicalFrameworkCreate, LogicalFrameworkUpdate,
    SpecificObjectiveCreate, SpecificObjectiveUpdate,
    ResultCreate, ResultUpdate,
    ActivityCreate, ActivityUpdate,
    IndicatorCreate, IndicatorUpdate, IndicatorUpdateCreate,
    FrameworkSummary
)


class LogicalFrameworkService:
    def __init__(self, db: Session):
        self.db = db

    # ======================== Framework Methods ========================

    def get_framework_by_project(self, project_id: int) -> LogicalFramework | None:
        """Get full framework with all nested data"""
        query = (
            select(LogicalFramework)
            .options(
                selectinload(LogicalFramework.indicators),
                selectinload(LogicalFramework.specific_objectives)
                .selectinload(SpecificObjective.indicators),
                selectinload(LogicalFramework.specific_objectives)
                .selectinload(SpecificObjective.results)
                .selectinload(Result.indicators),
                selectinload(LogicalFramework.specific_objectives)
                .selectinload(SpecificObjective.results)
                .selectinload(Result.activities)
                .selectinload(Activity.indicators),
            )
            .where(LogicalFramework.project_id == project_id)
        )
        return self.db.execute(query).scalar_one_or_none()

    def create_or_update_framework(
        self, project_id: int, data: LogicalFrameworkUpdate
    ) -> LogicalFramework:
        """Create or update a logical framework for a project"""
        framework = self.get_framework_by_project(project_id)

        if framework:
            # Update existing
            if data.objetivo_general is not None:
                framework.objetivo_general = data.objetivo_general
        else:
            # Create new
            framework = LogicalFramework(
                project_id=project_id,
                objetivo_general=data.objetivo_general
            )
            self.db.add(framework)

        self.db.commit()
        self.db.refresh(framework)
        return framework

    def get_framework_summary(self, project_id: int) -> FrameworkSummary:
        """Get summary statistics for a framework"""
        framework = self.get_framework_by_project(project_id)

        if not framework:
            return FrameworkSummary()

        total_objectives = 0
        total_results = 0
        total_activities = 0
        activities_completed = 0
        activities_in_progress = 0
        activities_pending = 0
        total_indicators = len(framework.indicators)  # General-level indicators
        indicators_updated = sum(1 for i in framework.indicators if i.valor_actual)
        completion_values = []

        for obj in framework.specific_objectives:
            total_objectives += 1
            total_indicators += len(obj.indicators)
            indicators_updated += sum(1 for i in obj.indicators if i.valor_actual)

            for indicator in obj.indicators:
                if indicator.porcentaje_cumplimiento is not None:
                    completion_values.append(indicator.porcentaje_cumplimiento)

            for result in obj.results:
                total_results += 1
                total_indicators += len(result.indicators)
                indicators_updated += sum(1 for i in result.indicators if i.valor_actual)

                for indicator in result.indicators:
                    if indicator.porcentaje_cumplimiento is not None:
                        completion_values.append(indicator.porcentaje_cumplimiento)

                for activity in result.activities:
                    total_activities += 1
                    total_indicators += len(activity.indicators)
                    indicators_updated += sum(1 for i in activity.indicators if i.valor_actual)

                    for indicator in activity.indicators:
                        if indicator.porcentaje_cumplimiento is not None:
                            completion_values.append(indicator.porcentaje_cumplimiento)

                    if activity.estado == EstadoActividad.completada:
                        activities_completed += 1
                    elif activity.estado == EstadoActividad.en_curso:
                        activities_in_progress += 1
                    elif activity.estado == EstadoActividad.pendiente:
                        activities_pending += 1

        # Add general-level indicator completion values
        for indicator in framework.indicators:
            if indicator.porcentaje_cumplimiento is not None:
                completion_values.append(indicator.porcentaje_cumplimiento)

        average_completion = None
        if completion_values:
            average_completion = sum(completion_values) / len(completion_values)

        return FrameworkSummary(
            total_objectives=total_objectives,
            total_results=total_results,
            total_activities=total_activities,
            activities_completed=activities_completed,
            activities_in_progress=activities_in_progress,
            activities_pending=activities_pending,
            total_indicators=total_indicators,
            indicators_updated=indicators_updated,
            average_completion=average_completion
        )

    # ======================== Specific Objective Methods ========================

    def add_objective(
        self, project_id: int, data: SpecificObjectiveCreate
    ) -> SpecificObjective | None:
        """Add a specific objective to a framework"""
        framework = self.get_framework_by_project(project_id)
        if not framework:
            # Create framework first
            framework = self.create_or_update_framework(
                project_id,
                LogicalFrameworkUpdate(objetivo_general=None)
            )

        objective = SpecificObjective(
            framework_id=framework.id,
            numero=data.numero,
            descripcion=data.descripcion
        )
        self.db.add(objective)
        self.db.commit()
        self.db.refresh(objective)
        return objective

    def update_objective(
        self, objective_id: int, data: SpecificObjectiveUpdate
    ) -> SpecificObjective | None:
        """Update a specific objective"""
        objective = self.db.get(SpecificObjective, objective_id)
        if not objective:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(objective, field, value)

        self.db.commit()
        self.db.refresh(objective)
        return objective

    def delete_objective(self, objective_id: int) -> bool:
        """Delete a specific objective and all its children"""
        objective = self.db.get(SpecificObjective, objective_id)
        if not objective:
            return False

        self.db.delete(objective)
        self.db.commit()
        return True

    def get_objective(self, objective_id: int) -> SpecificObjective | None:
        """Get a specific objective with its children"""
        query = (
            select(SpecificObjective)
            .options(
                selectinload(SpecificObjective.indicators),
                selectinload(SpecificObjective.results)
                .selectinload(Result.indicators),
                selectinload(SpecificObjective.results)
                .selectinload(Result.activities)
                .selectinload(Activity.indicators),
            )
            .where(SpecificObjective.id == objective_id)
        )
        return self.db.execute(query).scalar_one_or_none()

    # ======================== Result Methods ========================

    def add_result(self, objective_id: int, data: ResultCreate) -> Result | None:
        """Add a result to a specific objective"""
        objective = self.db.get(SpecificObjective, objective_id)
        if not objective:
            return None

        result = Result(
            objective_id=objective_id,
            numero=data.numero,
            descripcion=data.descripcion
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        return result

    def update_result(self, result_id: int, data: ResultUpdate) -> Result | None:
        """Update a result"""
        result = self.db.get(Result, result_id)
        if not result:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(result, field, value)

        self.db.commit()
        self.db.refresh(result)
        return result

    def delete_result(self, result_id: int) -> bool:
        """Delete a result and all its children"""
        result = self.db.get(Result, result_id)
        if not result:
            return False

        self.db.delete(result)
        self.db.commit()
        return True

    def get_result(self, result_id: int) -> Result | None:
        """Get a result with its children"""
        query = (
            select(Result)
            .options(
                selectinload(Result.indicators),
                selectinload(Result.activities)
                .selectinload(Activity.indicators),
            )
            .where(Result.id == result_id)
        )
        return self.db.execute(query).scalar_one_or_none()

    # ======================== Activity Methods ========================

    def add_activity(self, result_id: int, data: ActivityCreate) -> Activity | None:
        """Add an activity to a result"""
        result = self.db.get(Result, result_id)
        if not result:
            return None

        activity = Activity(
            result_id=result_id,
            numero=data.numero,
            descripcion=data.descripcion,
            fecha_inicio_prevista=data.fecha_inicio_prevista,
            fecha_fin_prevista=data.fecha_fin_prevista,
            estado=data.estado
        )
        self.db.add(activity)
        self.db.commit()
        self.db.refresh(activity)
        return activity

    def update_activity(self, activity_id: int, data: ActivityUpdate) -> Activity | None:
        """Update an activity with auto-dating for status changes"""
        activity = self.db.get(Activity, activity_id)
        if not activity:
            return None

        old_estado = activity.estado

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(activity, field, value)

        # Auto-set dates based on status changes
        new_estado = data.estado
        if new_estado and new_estado != old_estado:
            if new_estado == EstadoActividad.en_curso and not activity.fecha_inicio_real:
                activity.fecha_inicio_real = date.today()
            elif new_estado == EstadoActividad.completada and not activity.fecha_fin_real:
                activity.fecha_fin_real = date.today()

        self.db.commit()
        self.db.refresh(activity)
        return activity

    def delete_activity(self, activity_id: int) -> bool:
        """Delete an activity"""
        activity = self.db.get(Activity, activity_id)
        if not activity:
            return False

        self.db.delete(activity)
        self.db.commit()
        return True

    def get_activity(self, activity_id: int) -> Activity | None:
        """Get an activity with its indicators"""
        query = (
            select(Activity)
            .options(selectinload(Activity.indicators))
            .where(Activity.id == activity_id)
        )
        return self.db.execute(query).scalar_one_or_none()

    # ======================== Indicator Methods ========================

    def _calculate_percentage(
        self, valor_base: str | None, valor_meta: str | None, valor_actual: str | None
    ) -> Decimal | None:
        """Calculate percentage completion if values are numeric"""
        try:
            if not all([valor_base, valor_meta, valor_actual]):
                return None

            base = Decimal(valor_base.replace(",", "."))
            meta = Decimal(valor_meta.replace(",", "."))
            actual = Decimal(valor_actual.replace(",", "."))

            if meta == base:
                return None

            percentage = ((actual - base) / (meta - base)) * 100
            # Cap at 0-100 range (or allow > 100 for over-achievement)
            return max(Decimal("0"), percentage)
        except (InvalidOperation, ValueError, AttributeError):
            return None

    def create_indicator(self, data: IndicatorCreate) -> Indicator:
        """Create an indicator at any level"""
        # Calculate initial percentage if values provided
        porcentaje = self._calculate_percentage(
            data.valor_base, data.valor_meta, data.valor_actual
        )

        indicator = Indicator(
            framework_id=data.framework_id,
            objective_id=data.objective_id,
            result_id=data.result_id,
            activity_id=data.activity_id,
            codigo=data.codigo,
            descripcion=data.descripcion,
            unidad_medida=data.unidad_medida,
            fuente_verificacion=data.fuente_verificacion,
            valor_base=data.valor_base,
            valor_meta=data.valor_meta,
            valor_actual=data.valor_actual,
            porcentaje_cumplimiento=porcentaje
        )
        self.db.add(indicator)
        self.db.commit()
        self.db.refresh(indicator)
        return indicator

    def update_indicator(self, indicator_id: int, data: IndicatorUpdate) -> Indicator | None:
        """Update indicator metadata (not value - use update_indicator_value for that)"""
        indicator = self.db.get(Indicator, indicator_id)
        if not indicator:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(indicator, field, value)

        # Recalculate percentage if base or meta changed
        if "valor_base" in update_data or "valor_meta" in update_data:
            indicator.porcentaje_cumplimiento = self._calculate_percentage(
                indicator.valor_base, indicator.valor_meta, indicator.valor_actual
            )

        self.db.commit()
        self.db.refresh(indicator)
        return indicator

    def update_indicator_value(
        self, indicator_id: int, data: IndicatorUpdateCreate
    ) -> Indicator | None:
        """Update indicator value and create audit log"""
        indicator = self.db.get(Indicator, indicator_id)
        if not indicator:
            return None

        # Store old values for audit
        old_valor = indicator.valor_actual
        old_porcentaje = indicator.porcentaje_cumplimiento

        # Update value
        indicator.valor_actual = data.valor_nuevo

        # Calculate new percentage
        new_porcentaje = self._calculate_percentage(
            indicator.valor_base, indicator.valor_meta, data.valor_nuevo
        )
        indicator.porcentaje_cumplimiento = new_porcentaje

        # Create audit log
        audit = IndicatorUpdateModel(
            indicator_id=indicator_id,
            valor_anterior=old_valor,
            valor_nuevo=data.valor_nuevo,
            porcentaje_anterior=old_porcentaje,
            porcentaje_nuevo=new_porcentaje,
            observaciones=data.observaciones,
            updated_by=data.updated_by
        )
        self.db.add(audit)

        self.db.commit()
        self.db.refresh(indicator)
        return indicator

    def delete_indicator(self, indicator_id: int) -> bool:
        """Delete an indicator"""
        indicator = self.db.get(Indicator, indicator_id)
        if not indicator:
            return False

        self.db.delete(indicator)
        self.db.commit()
        return True

    def get_indicator(self, indicator_id: int) -> Indicator | None:
        """Get an indicator with its update history"""
        query = (
            select(Indicator)
            .options(selectinload(Indicator.updates))
            .where(Indicator.id == indicator_id)
        )
        return self.db.execute(query).scalar_one_or_none()

    def get_indicator_history(self, indicator_id: int) -> list[IndicatorUpdateModel]:
        """Get the update history for an indicator"""
        query = (
            select(IndicatorUpdateModel)
            .where(IndicatorUpdateModel.indicator_id == indicator_id)
            .order_by(IndicatorUpdateModel.created_at.desc())
        )
        return list(self.db.execute(query).scalars().all())

    # ======================== Helper Methods ========================

    def get_next_objective_number(self, project_id: int) -> int:
        """Get the next objective number for a project"""
        framework = self.get_framework_by_project(project_id)
        if not framework or not framework.specific_objectives:
            return 1
        return max(obj.numero for obj in framework.specific_objectives) + 1

    def get_next_result_number(self, objective_id: int) -> str:
        """Get the next result number for an objective"""
        objective = self.get_objective(objective_id)
        if not objective or not objective.results:
            return "R1"

        # Parse existing numbers and find max
        max_num = 0
        for result in objective.results:
            try:
                num = int(result.numero.replace("R", ""))
                max_num = max(max_num, num)
            except ValueError:
                pass
        return f"R{max_num + 1}"

    def get_next_activity_number(self, result_id: int) -> str:
        """Get the next activity number for a result"""
        result = self.get_result(result_id)
        if not result or not result.activities:
            # Get the result number to build activity number
            result_num = result.numero.replace("R", "") if result else "1"
            return f"A{result_num}.1"

        # Parse existing numbers and find max
        max_num = 0
        for activity in result.activities:
            try:
                # Format: A1.2 -> get the 2
                parts = activity.numero.replace("A", "").split(".")
                if len(parts) == 2:
                    max_num = max(max_num, int(parts[1]))
            except ValueError:
                pass

        result_num = result.numero.replace("R", "")
        return f"A{result_num}.{max_num + 1}"

    def get_next_indicator_code(self, framework_id: int) -> str:
        """Get the next indicator code for a framework"""
        query = (
            select(func.count(Indicator.id))
            .where(Indicator.framework_id == framework_id)
        )
        count = self.db.execute(query).scalar() or 0
        return f"IOV{count + 1}"
