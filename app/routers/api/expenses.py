from datetime import date
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.expense import UbicacionGasto, EstadoGasto
from app.models.user import User
from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import Permiso
from app.services.expense_service import ExpenseService
from app.schemas.expense import (
    ExpenseCreate,
    ExpenseUpdate,
    ExpenseResponse,
    ExpenseSummary,
    BudgetLineBalance,
    ExpenseFilters,
    BudgetLineInfo,
)

router = APIRouter()


def get_service(db: Session = Depends(get_db)) -> ExpenseService:
    return ExpenseService(db)


def expense_to_response(expense) -> ExpenseResponse:
    """Convert Expense model to ExpenseResponse schema"""
    return ExpenseResponse(
        id=expense.id,
        project_id=expense.project_id,
        budget_line_id=expense.budget_line_id,
        fecha_factura=expense.fecha_factura,
        concepto=expense.concepto,
        expedidor=expense.expedidor,
        persona=expense.persona,
        cantidad_original=expense.cantidad_original,
        moneda_original=expense.moneda_original,
        tipo_cambio=expense.tipo_cambio,
        cantidad_euros=expense.cantidad_euros,
        porcentaje=expense.porcentaje,
        financiado_por=expense.financiado_por,
        ubicacion=expense.ubicacion,
        estado=expense.estado,
        comprobacion=expense.comprobacion,
        fecha_revision=expense.fecha_revision,
        observaciones=expense.observaciones,
        documento_path=expense.documento_path,
        created_at=expense.created_at,
        updated_at=expense.updated_at,
        cantidad_imputable=expense.cantidad_imputable,
        budget_line=BudgetLineInfo(
            id=expense.budget_line.id,
            code=expense.budget_line.code,
            name=expense.budget_line.name,
        ) if expense.budget_line else None,
    )


@router.get("/projects/{project_id}/expenses", response_model=list[ExpenseResponse])
def list_project_expenses(
    project_id: int,
    budget_line_id: int | None = Query(None),
    estado: EstadoGasto | None = Query(None),
    ubicacion: UbicacionGasto | None = Query(None),
    fecha_desde: date | None = Query(None),
    fecha_hasta: date | None = Query(None),
    user: User = Depends(require_permission(Permiso.gasto_ver)),
    service: ExpenseService = Depends(get_service),
):
    """List all expenses for a project with optional filters"""
    filters = ExpenseFilters(
        budget_line_id=budget_line_id,
        estado=estado,
        ubicacion=ubicacion,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    expenses = service.get_project_expenses(project_id, filters)
    return [expense_to_response(e) for e in expenses]


@router.post("/projects/{project_id}/expenses", response_model=ExpenseResponse)
def create_expense(
    project_id: int,
    data: ExpenseCreate,
    user: User = Depends(require_permission(Permiso.gasto_crear)),
    service: ExpenseService = Depends(get_service),
):
    """Create a new expense for a project"""
    try:
        expense = service.create_expense(project_id, data)
        return expense_to_response(expense)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/expenses/{expense_id}", response_model=ExpenseResponse)
def get_expense(
    expense_id: int,
    user: User = Depends(require_permission(Permiso.gasto_ver)),
    service: ExpenseService = Depends(get_service),
):
    """Get a specific expense"""
    expense = service.get_expense_by_id(expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    return expense_to_response(expense)


@router.put("/expenses/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    expense_id: int,
    data: ExpenseUpdate,
    user: User = Depends(require_permission(Permiso.gasto_crear)),
    service: ExpenseService = Depends(get_service),
):
    """Update an expense"""
    try:
        expense = service.update_expense(expense_id, data)
        if not expense:
            raise HTTPException(status_code=404, detail="Gasto no encontrado")
        return expense_to_response(expense)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/expenses/{expense_id}")
def delete_expense(
    expense_id: int,
    user: User = Depends(require_permission(Permiso.gasto_crear)),
    service: ExpenseService = Depends(get_service),
):
    """Delete an expense"""
    if not service.delete_expense(expense_id):
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    return {"message": "Gasto eliminado"}


@router.post("/expenses/{expense_id}/submit", response_model=ExpenseResponse)
def submit_expense(
    expense_id: int,
    user: User = Depends(require_permission(Permiso.gasto_crear)),
    service: ExpenseService = Depends(get_service),
):
    """Submit expense for review"""
    try:
        expense = service.submit_for_review(expense_id)
        if not expense:
            raise HTTPException(status_code=404, detail="Gasto no encontrado")
        return expense_to_response(expense)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/expenses/{expense_id}/validate", response_model=ExpenseResponse)
def validate_expense(
    expense_id: int,
    user: User = Depends(require_permission(Permiso.gasto_validar)),
    service: ExpenseService = Depends(get_service),
):
    """Validate an expense"""
    try:
        expense = service.validate_expense(expense_id)
        if not expense:
            raise HTTPException(status_code=404, detail="Gasto no encontrado")
        return expense_to_response(expense)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/expenses/{expense_id}/reject", response_model=ExpenseResponse)
def reject_expense(
    expense_id: int,
    reason: str | None = None,
    user: User = Depends(require_permission(Permiso.gasto_validar)),
    service: ExpenseService = Depends(get_service),
):
    """Reject an expense"""
    try:
        expense = service.reject_expense(expense_id, reason)
        if not expense:
            raise HTTPException(status_code=404, detail="Gasto no encontrado")
        return expense_to_response(expense)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/expenses/{expense_id}/justify", response_model=ExpenseResponse)
def justify_expense(
    expense_id: int,
    user: User = Depends(require_permission(Permiso.gasto_justificar)),
    service: ExpenseService = Depends(get_service),
):
    """Mark expense as justified"""
    try:
        expense = service.mark_as_justified(expense_id)
        if not expense:
            raise HTTPException(status_code=404, detail="Gasto no encontrado")
        return expense_to_response(expense)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/expenses/{expense_id}/revert", response_model=ExpenseResponse)
def revert_expense(
    expense_id: int,
    user: User = Depends(require_permission(Permiso.gasto_validar)),
    service: ExpenseService = Depends(get_service),
):
    """Revert expense to draft state"""
    try:
        expense = service.revert_to_draft(expense_id)
        if not expense:
            raise HTTPException(status_code=404, detail="Gasto no encontrado")
        return expense_to_response(expense)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/expenses/{expense_id}/upload-document")
def upload_document(
    expense_id: int,
    file: UploadFile = File(...),
    user: User = Depends(require_permission(Permiso.gasto_justificar)),
    service: ExpenseService = Depends(get_service),
):
    """Upload a document for an expense"""
    try:
        filepath = service.save_document(expense_id, file)
        return {"message": "Documento subido", "path": filepath}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/expenses/{expense_id}/document")
def delete_document(
    expense_id: int,
    user: User = Depends(require_permission(Permiso.gasto_crear)),
    service: ExpenseService = Depends(get_service),
):
    """Delete the document for an expense"""
    if not service.delete_document(expense_id):
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return {"message": "Documento eliminado"}


@router.get("/projects/{project_id}/expenses/summary", response_model=ExpenseSummary)
def get_expense_summary(
    project_id: int,
    user: User = Depends(require_permission(Permiso.gasto_ver)),
    service: ExpenseService = Depends(get_service),
):
    """Get expense summary for a project"""
    return service.get_expense_summary(project_id)


@router.get("/projects/{project_id}/budget-lines/balance", response_model=list[BudgetLineBalance])
def get_budget_lines_balance(
    project_id: int,
    user: User = Depends(require_permission(Permiso.gasto_ver)),
    service: ExpenseService = Depends(get_service),
):
    """Get budget lines with available balance"""
    return service.get_budget_lines_with_balance(project_id)
