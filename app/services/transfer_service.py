import os
import shutil
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from fastapi import UploadFile

from app.models.transfer import Transfer, EstadoTransferencia, get_moneda_for_pais
from app.models.project import Project
from app.models.expense import Expense, EstadoGasto, UbicacionGasto
from app.schemas.transfer import (
    TransferCreate,
    TransferUpdate,
    TransferSummary,
    ConfirmReceptionData,
)


class TransferService:
    def __init__(self, db: Session):
        self.db = db

    # CRUD Operations

    def get_project_transfers(self, project_id: int) -> list[Transfer]:
        """Get all transfers for a project ordered by numero."""
        query = (
            select(Transfer)
            .where(Transfer.project_id == project_id)
            .order_by(Transfer.numero)
        )
        return list(self.db.execute(query).scalars().all())

    def get_transfer_by_id(self, transfer_id: int) -> Transfer | None:
        """Get a single transfer by ID."""
        return self.db.get(Transfer, transfer_id)

    def create_transfer(self, project_id: int, data: TransferCreate) -> Transfer:
        """Create a new transfer with sequential numbering."""
        # Verify project exists
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError("Proyecto no encontrado")

        # Get next sequential number
        max_numero = self.db.execute(
            select(func.max(Transfer.numero)).where(Transfer.project_id == project_id)
        ).scalar() or 0
        next_numero = max_numero + 1

        # Validate budget availability
        summary = self.get_transfer_summary(project_id)
        if data.importe_euros > summary.total_pendiente:
            raise ValueError(
                f"El importe ({data.importe_euros} EUR) supera el presupuesto disponible "
                f"({summary.total_pendiente} EUR)"
            )

        # Get default local currency based on project country
        moneda_local = data.moneda_local
        if not moneda_local and project.pais:
            currency = get_moneda_for_pais(project.pais)
            if currency:
                moneda_local = currency.value

        transfer = Transfer(
            project_id=project_id,
            numero=next_numero,
            total_previstas=data.total_previstas,
            fecha_peticion=data.fecha_peticion,
            fecha_emision=data.fecha_emision,
            importe_euros=data.importe_euros,
            gastos_transferencia=data.gastos_transferencia,
            usa_moneda_intermedia=data.usa_moneda_intermedia,
            moneda_intermedia=data.moneda_intermedia,
            importe_moneda_intermedia=data.importe_moneda_intermedia,
            tipo_cambio_intermedio=data.tipo_cambio_intermedio,
            moneda_local=moneda_local,
            importe_moneda_local=data.importe_moneda_local,
            tipo_cambio_local=data.tipo_cambio_local,
            cuenta_origen=data.cuenta_origen or project.cuenta_bancaria,
            cuenta_destino=data.cuenta_destino,
            entidad_bancaria=data.entidad_bancaria,
            estado=EstadoTransferencia.solicitada,
            es_ultima=data.es_ultima,
            observaciones=data.observaciones,
        )
        self.db.add(transfer)
        self.db.commit()
        self.db.refresh(transfer)
        return transfer

    def update_transfer(self, transfer_id: int, data: TransferUpdate) -> Transfer | None:
        """Update a transfer (only allowed in solicitada or aprobada states)."""
        transfer = self.get_transfer_by_id(transfer_id)
        if not transfer:
            return None

        if transfer.estado not in (EstadoTransferencia.solicitada, EstadoTransferencia.aprobada):
            raise ValueError(
                "Solo se pueden editar transferencias en estado solicitada o aprobada"
            )

        # Validate budget if importe is being changed
        if data.importe_euros is not None and data.importe_euros != transfer.importe_euros:
            summary = self.get_transfer_summary(transfer.project_id)
            # Add back current transfer amount to available
            available = summary.total_pendiente + transfer.importe_euros
            if data.importe_euros > available:
                raise ValueError(
                    f"El importe ({data.importe_euros} EUR) supera el presupuesto disponible "
                    f"({available} EUR)"
                )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(transfer, field, value)

        self.db.commit()
        self.db.refresh(transfer)
        return transfer

    def delete_transfer(self, transfer_id: int) -> bool:
        """Delete a transfer (only allowed in solicitada state)."""
        transfer = self.get_transfer_by_id(transfer_id)
        if not transfer:
            return False

        if transfer.estado != EstadoTransferencia.solicitada:
            raise ValueError("Solo se pueden eliminar transferencias en estado solicitada")

        self.db.delete(transfer)
        self.db.commit()
        return True

    # State Transitions

    def approve_transfer(self, transfer_id: int) -> Transfer | None:
        """Approve a transfer: solicitada -> aprobada."""
        transfer = self.get_transfer_by_id(transfer_id)
        if not transfer:
            return None

        if transfer.estado != EstadoTransferencia.solicitada:
            raise ValueError("Solo se pueden aprobar transferencias en estado solicitada")

        transfer.estado = EstadoTransferencia.aprobada
        self.db.commit()
        self.db.refresh(transfer)
        return transfer

    def confirm_emission(self, transfer_id: int, fecha_emision: date | None = None) -> Transfer | None:
        """Confirm transfer emission: aprobada -> emitida."""
        transfer = self.get_transfer_by_id(transfer_id)
        if not transfer:
            return None

        if transfer.estado != EstadoTransferencia.aprobada:
            raise ValueError("Solo se pueden emitir transferencias en estado aprobada")

        # Require emission document before transitioning
        if not transfer.documento_emision_path:
            raise ValueError(
                "Debe adjuntar un justificante de emision para marcar la transferencia como emitida"
            )

        transfer.estado = EstadoTransferencia.emitida
        transfer.fecha_emision = fecha_emision or date.today()
        self.db.commit()
        self.db.refresh(transfer)
        return transfer

    def confirm_reception(
        self, transfer_id: int, data: ConfirmReceptionData | None = None
    ) -> Transfer | None:
        """Confirm transfer reception: emitida -> recibida."""
        transfer = self.get_transfer_by_id(transfer_id)
        if not transfer:
            return None

        if transfer.estado != EstadoTransferencia.emitida:
            raise ValueError("Solo se pueden confirmar recepciones de transferencias emitidas")

        # Require reception document before transitioning
        if not transfer.documento_recepcion_path:
            raise ValueError(
                "Debe adjuntar un justificante de recepcion para marcar la transferencia como recibida"
            )

        transfer.estado = EstadoTransferencia.recibida

        if data:
            transfer.fecha_recepcion = data.fecha_recepcion or date.today()
            if data.importe_moneda_local is not None:
                transfer.importe_moneda_local = data.importe_moneda_local
            if data.tipo_cambio_local is not None:
                transfer.tipo_cambio_local = data.tipo_cambio_local
        else:
            transfer.fecha_recepcion = date.today()

        self.db.commit()
        self.db.refresh(transfer)
        return transfer

    def close_transfer(self, transfer_id: int) -> Transfer | None:
        """Close a transfer: recibida -> cerrada."""
        transfer = self.get_transfer_by_id(transfer_id)
        if not transfer:
            return None

        if transfer.estado != EstadoTransferencia.recibida:
            raise ValueError("Solo se pueden cerrar transferencias en estado recibida")

        transfer.estado = EstadoTransferencia.cerrada
        self.db.commit()
        self.db.refresh(transfer)
        return transfer

    def revert_to_previous_state(self, transfer_id: int) -> Transfer | None:
        """Revert transfer to previous state."""
        transfer = self.get_transfer_by_id(transfer_id)
        if not transfer:
            return None

        state_transitions = {
            EstadoTransferencia.aprobada: EstadoTransferencia.solicitada,
            EstadoTransferencia.emitida: EstadoTransferencia.aprobada,
            EstadoTransferencia.recibida: EstadoTransferencia.emitida,
            EstadoTransferencia.cerrada: EstadoTransferencia.recibida,
        }

        if transfer.estado not in state_transitions:
            raise ValueError("No se puede revertir una transferencia en estado solicitada")

        previous_state = state_transitions[transfer.estado]

        # Clear dates when reverting from certain states
        if transfer.estado == EstadoTransferencia.emitida:
            transfer.fecha_emision = None
        elif transfer.estado == EstadoTransferencia.recibida:
            transfer.fecha_recepcion = None

        transfer.estado = previous_state
        self.db.commit()
        self.db.refresh(transfer)
        return transfer

    # Summary and Calculations

    def get_transfer_summary(self, project_id: int) -> TransferSummary:
        """Get transfer summary statistics for a project."""
        project = self.db.get(Project, project_id)
        if not project:
            return TransferSummary()

        summary = TransferSummary()
        summary.presupuesto_total = project.subvencion or Decimal("0")

        # Calculate validated Spain expenses
        spain_expenses_query = (
            select(func.sum(Expense.cantidad_euros * Expense.porcentaje / 100))
            .where(Expense.project_id == project_id)
            .where(Expense.ubicacion == UbicacionGasto.espana)
            .where(Expense.estado.in_([EstadoGasto.validado, EstadoGasto.justificado]))
        )
        spain_total = self.db.execute(spain_expenses_query).scalar() or Decimal("0")
        summary.gastos_espana_validados = spain_total

        # Budget available for transfers
        summary.presupuesto_a_transferir = summary.presupuesto_total - summary.gastos_espana_validados

        # Get transfers
        transfers = self.get_project_transfers(project_id)

        # States that count as "sent"
        sent_states = [
            EstadoTransferencia.emitida,
            EstadoTransferencia.recibida,
            EstadoTransferencia.cerrada,
        ]

        for transfer in transfers:
            if transfer.estado in sent_states:
                summary.total_enviado += transfer.importe_euros
                summary.transferencias_realizadas += 1
            summary.total_gastos_transferencia += transfer.gastos_transferencia or Decimal("0")

        # Get max total_previstas from transfers
        if transfers:
            summary.transferencias_previstas = max(t.total_previstas for t in transfers)

        # Calculate pending
        summary.total_pendiente = summary.presupuesto_a_transferir - summary.total_enviado

        # Calculate percentage
        if summary.presupuesto_a_transferir > 0:
            summary.porcentaje_transferido = (
                summary.total_enviado / summary.presupuesto_a_transferir * 100
            )

        return summary

    def get_default_moneda_local(self, project_id: int) -> str | None:
        """Get the default local currency based on project country."""
        project = self.db.get(Project, project_id)
        if project and project.pais:
            currency = get_moneda_for_pais(project.pais)
            if currency:
                return currency.value
        return None

    # Document Management

    def _get_transfer_upload_dir(self, project_id: int, transfer_id: int) -> str:
        """Get the upload directory for a transfer."""
        return f"uploads/{project_id}/transfers/{transfer_id}"

    def save_emission_document(
        self, transfer_id: int, file: UploadFile
    ) -> Transfer | None:
        """Save emission document for a transfer."""
        transfer = self.get_transfer_by_id(transfer_id)
        if not transfer:
            return None

        # Allow upload when in aprobada state (before emission) or later
        if transfer.estado not in (
            EstadoTransferencia.aprobada,
            EstadoTransferencia.emitida,
            EstadoTransferencia.recibida,
            EstadoTransferencia.cerrada,
        ):
            raise ValueError(
                "Solo se pueden adjuntar documentos de emision a transferencias aprobadas o posteriores"
            )

        # Create directory
        upload_dir = self._get_transfer_upload_dir(transfer.project_id, transfer_id)
        os.makedirs(upload_dir, exist_ok=True)

        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        original_filename = file.filename or "document"
        safe_filename = original_filename.replace(" ", "_").replace("/", "_")
        filename = f"emision_{timestamp}_{safe_filename}"
        filepath = os.path.join(upload_dir, filename)

        # Delete old file if exists
        if transfer.documento_emision_path and os.path.exists(transfer.documento_emision_path):
            os.remove(transfer.documento_emision_path)

        # Save new file
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Update transfer
        transfer.documento_emision_path = filepath
        transfer.documento_emision_filename = original_filename
        self.db.commit()
        self.db.refresh(transfer)
        return transfer

    def save_reception_document(
        self, transfer_id: int, file: UploadFile
    ) -> Transfer | None:
        """Save reception document for a transfer."""
        transfer = self.get_transfer_by_id(transfer_id)
        if not transfer:
            return None

        # Allow upload when in emitida state (before reception) or later
        if transfer.estado not in (
            EstadoTransferencia.emitida,
            EstadoTransferencia.recibida,
            EstadoTransferencia.cerrada,
        ):
            raise ValueError(
                "Solo se pueden adjuntar documentos de recepcion a transferencias emitidas o posteriores"
            )

        # Create directory
        upload_dir = self._get_transfer_upload_dir(transfer.project_id, transfer_id)
        os.makedirs(upload_dir, exist_ok=True)

        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        original_filename = file.filename or "document"
        safe_filename = original_filename.replace(" ", "_").replace("/", "_")
        filename = f"recepcion_{timestamp}_{safe_filename}"
        filepath = os.path.join(upload_dir, filename)

        # Delete old file if exists
        if transfer.documento_recepcion_path and os.path.exists(transfer.documento_recepcion_path):
            os.remove(transfer.documento_recepcion_path)

        # Save new file
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Update transfer
        transfer.documento_recepcion_path = filepath
        transfer.documento_recepcion_filename = original_filename
        self.db.commit()
        self.db.refresh(transfer)
        return transfer

    def delete_emission_document(self, transfer_id: int) -> Transfer | None:
        """Delete emission document from a transfer."""
        transfer = self.get_transfer_by_id(transfer_id)
        if not transfer:
            return None

        if transfer.documento_emision_path and os.path.exists(transfer.documento_emision_path):
            os.remove(transfer.documento_emision_path)

        transfer.documento_emision_path = None
        transfer.documento_emision_filename = None
        self.db.commit()
        self.db.refresh(transfer)
        return transfer

    def delete_reception_document(self, transfer_id: int) -> Transfer | None:
        """Delete reception document from a transfer."""
        transfer = self.get_transfer_by_id(transfer_id)
        if not transfer:
            return None

        if transfer.documento_recepcion_path and os.path.exists(transfer.documento_recepcion_path):
            os.remove(transfer.documento_recepcion_path)

        transfer.documento_recepcion_path = None
        transfer.documento_recepcion_filename = None
        self.db.commit()
        self.db.refresh(transfer)
        return transfer
