from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.transfer_service import TransferService
from app.schemas.transfer import (
    TransferCreate,
    TransferUpdate,
    TransferResponse,
    TransferSummary,
    ConfirmReceptionData,
)

router = APIRouter()


def get_service(db: Session = Depends(get_db)) -> TransferService:
    return TransferService(db)


def transfer_to_response(transfer) -> TransferResponse:
    """Convert Transfer model to TransferResponse schema."""
    return TransferResponse(
        id=transfer.id,
        project_id=transfer.project_id,
        numero=transfer.numero,
        total_previstas=transfer.total_previstas,
        numero_display=transfer.numero_display,
        fecha_peticion=transfer.fecha_peticion,
        fecha_emision=transfer.fecha_emision,
        fecha_recepcion=transfer.fecha_recepcion,
        importe_euros=transfer.importe_euros,
        gastos_transferencia=transfer.gastos_transferencia,
        importe_neto=transfer.importe_neto,
        usa_moneda_intermedia=transfer.usa_moneda_intermedia,
        moneda_intermedia=transfer.moneda_intermedia,
        importe_moneda_intermedia=transfer.importe_moneda_intermedia,
        tipo_cambio_intermedio=transfer.tipo_cambio_intermedio,
        moneda_local=transfer.moneda_local,
        importe_moneda_local=transfer.importe_moneda_local,
        tipo_cambio_local=transfer.tipo_cambio_local,
        cuenta_origen=transfer.cuenta_origen,
        cuenta_destino=transfer.cuenta_destino,
        entidad_bancaria=transfer.entidad_bancaria,
        estado=transfer.estado,
        es_ultima=transfer.es_ultima,
        observaciones=transfer.observaciones,
        created_at=transfer.created_at,
        updated_at=transfer.updated_at,
    )


@router.get("/projects/{project_id}/transfers", response_model=list[TransferResponse])
def list_project_transfers(
    project_id: int,
    service: TransferService = Depends(get_service),
):
    """List all transfers for a project."""
    transfers = service.get_project_transfers(project_id)
    return [transfer_to_response(t) for t in transfers]


@router.post("/projects/{project_id}/transfers", response_model=TransferResponse, status_code=201)
def create_transfer(
    project_id: int,
    data: TransferCreate,
    service: TransferService = Depends(get_service),
):
    """Create a new transfer for a project."""
    try:
        transfer = service.create_transfer(project_id, data)
        return transfer_to_response(transfer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/transfers/summary", response_model=TransferSummary)
def get_transfer_summary(
    project_id: int,
    service: TransferService = Depends(get_service),
):
    """Get transfer summary for a project."""
    return service.get_transfer_summary(project_id)


@router.get("/transfers/{transfer_id}", response_model=TransferResponse)
def get_transfer(
    transfer_id: int,
    service: TransferService = Depends(get_service),
):
    """Get a specific transfer."""
    transfer = service.get_transfer_by_id(transfer_id)
    if not transfer:
        raise HTTPException(status_code=404, detail="Transferencia no encontrada")
    return transfer_to_response(transfer)


@router.put("/transfers/{transfer_id}", response_model=TransferResponse)
def update_transfer(
    transfer_id: int,
    data: TransferUpdate,
    service: TransferService = Depends(get_service),
):
    """Update a transfer."""
    try:
        transfer = service.update_transfer(transfer_id, data)
        if not transfer:
            raise HTTPException(status_code=404, detail="Transferencia no encontrada")
        return transfer_to_response(transfer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/transfers/{transfer_id}")
def delete_transfer(
    transfer_id: int,
    service: TransferService = Depends(get_service),
):
    """Delete a transfer."""
    try:
        if not service.delete_transfer(transfer_id):
            raise HTTPException(status_code=404, detail="Transferencia no encontrada")
        return {"message": "Transferencia eliminada"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/transfers/{transfer_id}/approve", response_model=TransferResponse)
def approve_transfer(
    transfer_id: int,
    service: TransferService = Depends(get_service),
):
    """Approve a transfer."""
    try:
        transfer = service.approve_transfer(transfer_id)
        if not transfer:
            raise HTTPException(status_code=404, detail="Transferencia no encontrada")
        return transfer_to_response(transfer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/transfers/{transfer_id}/confirm-emission", response_model=TransferResponse)
def confirm_emission(
    transfer_id: int,
    fecha_emision: date | None = Query(None),
    service: TransferService = Depends(get_service),
):
    """Confirm transfer emission."""
    try:
        transfer = service.confirm_emission(transfer_id, fecha_emision)
        if not transfer:
            raise HTTPException(status_code=404, detail="Transferencia no encontrada")
        return transfer_to_response(transfer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/transfers/{transfer_id}/confirm-reception", response_model=TransferResponse)
def confirm_reception(
    transfer_id: int,
    data: ConfirmReceptionData | None = None,
    service: TransferService = Depends(get_service),
):
    """Confirm transfer reception."""
    try:
        transfer = service.confirm_reception(transfer_id, data)
        if not transfer:
            raise HTTPException(status_code=404, detail="Transferencia no encontrada")
        return transfer_to_response(transfer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/transfers/{transfer_id}/close", response_model=TransferResponse)
def close_transfer(
    transfer_id: int,
    service: TransferService = Depends(get_service),
):
    """Close a transfer."""
    try:
        transfer = service.close_transfer(transfer_id)
        if not transfer:
            raise HTTPException(status_code=404, detail="Transferencia no encontrada")
        return transfer_to_response(transfer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/transfers/{transfer_id}/revert", response_model=TransferResponse)
def revert_transfer(
    transfer_id: int,
    service: TransferService = Depends(get_service),
):
    """Revert a transfer to previous state."""
    try:
        transfer = service.revert_to_previous_state(transfer_id)
        if not transfer:
            raise HTTPException(status_code=404, detail="Transferencia no encontrada")
        return transfer_to_response(transfer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
