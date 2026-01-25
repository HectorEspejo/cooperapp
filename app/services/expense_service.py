import os
import shutil
from datetime import datetime
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from fastapi import UploadFile

from app.models.expense import Expense, UbicacionGasto, EstadoGasto
from app.models.budget import ProjectBudgetLine
from app.models.project import Project
from app.schemas.expense import (
    ExpenseCreate,
    ExpenseUpdate,
    ExpenseSummary,
    BudgetLineBalance,
    ExpenseFilters,
)


class ExpenseService:
    def __init__(self, db: Session):
        self.db = db

    # CRUD Operations
    def get_project_expenses(
        self, project_id: int, filters: ExpenseFilters | None = None
    ) -> list[Expense]:
        """Get all expenses for a project with optional filters"""
        query = (
            select(Expense)
            .where(Expense.project_id == project_id)
            .order_by(Expense.fecha_factura.desc(), Expense.id.desc())
        )

        if filters:
            if filters.budget_line_id:
                query = query.where(Expense.budget_line_id == filters.budget_line_id)
            if filters.estado:
                query = query.where(Expense.estado == filters.estado)
            if filters.ubicacion:
                query = query.where(Expense.ubicacion == filters.ubicacion)
            if filters.fecha_desde:
                query = query.where(Expense.fecha_factura >= filters.fecha_desde)
            if filters.fecha_hasta:
                query = query.where(Expense.fecha_factura <= filters.fecha_hasta)

        return list(self.db.execute(query).scalars().all())

    def get_expense_by_id(self, expense_id: int) -> Expense | None:
        """Get a single expense by ID"""
        return self.db.get(Expense, expense_id)

    def create_expense(self, project_id: int, data: ExpenseCreate) -> Expense:
        """Create a new expense"""
        # Verify budget line belongs to project
        budget_line = self.db.get(ProjectBudgetLine, data.budget_line_id)
        if not budget_line or budget_line.project_id != project_id:
            raise ValueError("Partida presupuestaria no encontrada para este proyecto")

        expense = Expense(
            project_id=project_id,
            budget_line_id=data.budget_line_id,
            fecha_factura=data.fecha_factura,
            concepto=data.concepto,
            expedidor=data.expedidor,
            persona=data.persona,
            cantidad_original=data.cantidad_original,
            moneda_original=data.moneda_original,
            tipo_cambio=data.tipo_cambio,
            cantidad_euros=data.cantidad_euros,
            porcentaje=data.porcentaje,
            financiado_por=data.financiado_por,
            ubicacion=data.ubicacion,
            estado=EstadoGasto.borrador,
            observaciones=data.observaciones,
        )
        self.db.add(expense)
        self.db.commit()
        self.db.refresh(expense)
        return expense

    def update_expense(self, expense_id: int, data: ExpenseUpdate) -> Expense | None:
        """Update an expense (only allowed in borrador state)"""
        expense = self.get_expense_by_id(expense_id)
        if not expense:
            return None

        if expense.estado != EstadoGasto.borrador:
            raise ValueError("Solo se pueden editar gastos en estado borrador")

        # If changing budget line, verify it belongs to same project
        if data.budget_line_id:
            budget_line = self.db.get(ProjectBudgetLine, data.budget_line_id)
            if not budget_line or budget_line.project_id != expense.project_id:
                raise ValueError("Partida presupuestaria no encontrada para este proyecto")

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(expense, field, value)

        self.db.commit()
        self.db.refresh(expense)
        return expense

    def delete_expense(self, expense_id: int) -> bool:
        """Delete an expense"""
        expense = self.get_expense_by_id(expense_id)
        if not expense:
            return False

        # If expense was validated, revert budget
        if expense.estado == EstadoGasto.validado:
            self._update_budget_line_executed(expense, add=False)

        # Delete associated document if exists
        if expense.documento_path:
            self._delete_document_file(expense.documento_path)

        self.db.delete(expense)
        self.db.commit()
        return True

    # State Transitions
    def submit_for_review(self, expense_id: int) -> Expense | None:
        """Submit expense for review (borrador -> pendiente_revision)"""
        expense = self.get_expense_by_id(expense_id)
        if not expense:
            return None

        if expense.estado != EstadoGasto.borrador:
            raise ValueError("Solo se pueden enviar a revisión gastos en estado borrador")

        expense.estado = EstadoGasto.pendiente_revision
        self.db.commit()
        self.db.refresh(expense)
        return expense

    def validate_expense(self, expense_id: int) -> Expense | None:
        """Validate an expense and update budget line executed amounts"""
        expense = self.get_expense_by_id(expense_id)
        if not expense:
            return None

        if expense.estado not in (EstadoGasto.borrador, EstadoGasto.pendiente_revision):
            raise ValueError("Solo se pueden validar gastos en estado borrador o pendiente de revisión")

        # Update budget line executed amount
        self._update_budget_line_executed(expense, add=True)

        expense.estado = EstadoGasto.validado
        expense.fecha_revision = datetime.utcnow()
        self.db.commit()
        self.db.refresh(expense)
        return expense

    def reject_expense(self, expense_id: int, reason: str | None = None) -> Expense | None:
        """Reject an expense"""
        expense = self.get_expense_by_id(expense_id)
        if not expense:
            return None

        # If was validated, revert budget
        if expense.estado == EstadoGasto.validado:
            self._update_budget_line_executed(expense, add=False)

        expense.estado = EstadoGasto.rechazado
        expense.fecha_revision = datetime.utcnow()
        if reason:
            expense.observaciones = reason
        self.db.commit()
        self.db.refresh(expense)
        return expense

    def mark_as_justified(self, expense_id: int) -> Expense | None:
        """Mark expense as justified (validado -> justificado)"""
        expense = self.get_expense_by_id(expense_id)
        if not expense:
            return None

        if expense.estado != EstadoGasto.validado:
            raise ValueError("Solo se pueden justificar gastos validados")

        expense.estado = EstadoGasto.justificado
        self.db.commit()
        self.db.refresh(expense)
        return expense

    def revert_to_draft(self, expense_id: int) -> Expense | None:
        """Revert expense to draft state"""
        expense = self.get_expense_by_id(expense_id)
        if not expense:
            return None

        # If was validated, revert budget
        if expense.estado == EstadoGasto.validado:
            self._update_budget_line_executed(expense, add=False)

        expense.estado = EstadoGasto.borrador
        expense.fecha_revision = None
        self.db.commit()
        self.db.refresh(expense)
        return expense

    # Budget Integration
    def _update_budget_line_executed(self, expense: Expense, add: bool = True) -> None:
        """Update budget line executed amount based on expense location"""
        budget_line = self.db.get(ProjectBudgetLine, expense.budget_line_id)
        if not budget_line:
            return

        amount = expense.cantidad_imputable
        if not add:
            amount = -amount

        if expense.ubicacion == UbicacionGasto.espana:
            budget_line.ejecutado_espana += amount
        else:
            budget_line.ejecutado_terreno += amount

        self.db.flush()

    def get_budget_lines_with_balance(self, project_id: int) -> list[BudgetLineBalance]:
        """Get budget lines with available balance for expense creation"""
        query = (
            select(ProjectBudgetLine)
            .where(ProjectBudgetLine.project_id == project_id)
            .order_by(ProjectBudgetLine.order)
        )
        lines = self.db.execute(query).scalars().all()

        return [
            BudgetLineBalance(
                id=line.id,
                code=line.code,
                name=line.name,
                aprobado=line.aprobado,
                ejecutado_espana=line.ejecutado_espana,
                ejecutado_terreno=line.ejecutado_terreno,
                disponible_espana=line.disponible_espana,
                disponible_terreno=line.disponible_terreno,
                is_spain_only=line.is_spain_only,
            )
            for line in lines
        ]

    # Document Management
    def save_document(self, expense_id: int, file: UploadFile) -> str:
        """Save document for an expense"""
        expense = self.get_expense_by_id(expense_id)
        if not expense:
            raise ValueError("Gasto no encontrado")

        # Delete existing document if any
        if expense.documento_path:
            self._delete_document_file(expense.documento_path)

        # Create directory structure: uploads/{project_id}/expenses/
        upload_dir = f"uploads/{expense.project_id}/expenses"
        os.makedirs(upload_dir, exist_ok=True)

        # Generate filename: {expense_id}_{timestamp}_{original_filename}
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        safe_filename = file.filename.replace(" ", "_") if file.filename else "document"
        filename = f"{expense_id}_{timestamp}_{safe_filename}"
        filepath = os.path.join(upload_dir, filename)

        # Save file
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        expense.documento_path = filepath
        self.db.commit()
        self.db.refresh(expense)

        return filepath

    def delete_document(self, expense_id: int) -> bool:
        """Delete document for an expense"""
        expense = self.get_expense_by_id(expense_id)
        if not expense or not expense.documento_path:
            return False

        self._delete_document_file(expense.documento_path)
        expense.documento_path = None
        self.db.commit()
        return True

    def _delete_document_file(self, filepath: str) -> None:
        """Delete a document file from disk"""
        if os.path.exists(filepath):
            os.remove(filepath)

    # Summary
    def get_expense_summary(self, project_id: int) -> ExpenseSummary:
        """Get expense summary statistics for a project"""
        expenses = self.get_project_expenses(project_id)

        summary = ExpenseSummary()
        summary.total_registrados = len(expenses)

        for expense in expenses:
            # Count by estado
            if expense.estado == EstadoGasto.borrador:
                summary.total_borradores += 1
            elif expense.estado == EstadoGasto.pendiente_revision:
                summary.total_pendientes += 1
            elif expense.estado == EstadoGasto.validado:
                summary.total_validados += 1
            elif expense.estado == EstadoGasto.rechazado:
                summary.total_rechazados += 1
            elif expense.estado == EstadoGasto.justificado:
                summary.total_justificados += 1

            # Sum amounts
            summary.importe_total += expense.cantidad_imputable

            if expense.estado in (EstadoGasto.validado, EstadoGasto.justificado):
                summary.importe_validado += expense.cantidad_imputable

            if expense.ubicacion == UbicacionGasto.espana:
                summary.importe_espana += expense.cantidad_imputable
            else:
                summary.importe_terreno += expense.cantidad_imputable

        return summary
