from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.postponement import Aplazamiento, EstadoAplazamiento
from app.models.project import Project
from app.schemas.postponement import AplazamientoCreate


class PostponementService:
    def __init__(self, db: Session):
        self.db = db

    def get_pending_for_project(self, project_id: int) -> Aplazamiento | None:
        return (
            self.db.query(Aplazamiento)
            .filter(
                Aplazamiento.project_id == project_id,
                Aplazamiento.estado == EstadoAplazamiento.pendiente,
            )
            .first()
        )

    def get_history(self, project_id: int) -> list[Aplazamiento]:
        return (
            self.db.query(Aplazamiento)
            .filter(
                Aplazamiento.project_id == project_id,
                Aplazamiento.estado != EstadoAplazamiento.pendiente,
            )
            .order_by(Aplazamiento.numero_secuencial)
            .all()
        )

    def get_all_for_project(self, project_id: int) -> list[Aplazamiento]:
        return (
            self.db.query(Aplazamiento)
            .filter(Aplazamiento.project_id == project_id)
            .order_by(Aplazamiento.numero_secuencial)
            .all()
        )

    def get_original_dates(self, project_id: int) -> dict | None:
        first = (
            self.db.query(Aplazamiento)
            .filter(
                Aplazamiento.project_id == project_id,
                Aplazamiento.numero_secuencial == 1,
            )
            .first()
        )
        if not first:
            return None
        return {
            "fecha_finalizacion": first.fecha_finalizacion_anterior,
            "fecha_justificacion": first.fecha_justificacion_anterior,
        }

    def create(
        self, project_id: int, solicitante_id: str, data: AplazamientoCreate
    ) -> Aplazamiento:
        project = self.db.query(Project).get(project_id)
        if not project:
            raise ValueError("Proyecto no encontrado")

        pending = self.get_pending_for_project(project_id)
        if pending:
            raise ValueError("Ya existe una solicitud de aplazamiento pendiente para este proyecto")

        max_seq = (
            self.db.query(func.max(Aplazamiento.numero_secuencial))
            .filter(Aplazamiento.project_id == project_id)
            .scalar()
        ) or 0

        aplazamiento = Aplazamiento(
            project_id=project_id,
            numero_secuencial=max_seq + 1,
            fecha_finalizacion_anterior=project.fecha_finalizacion,
            fecha_justificacion_anterior=project.fecha_justificacion,
            fecha_finalizacion_nueva=data.fecha_finalizacion_nueva,
            fecha_justificacion_nueva=data.fecha_justificacion_nueva,
            estado=EstadoAplazamiento.pendiente,
            motivo=data.motivo,
            solicitante_id=solicitante_id,
        )
        self.db.add(aplazamiento)
        self.db.commit()
        self.db.refresh(aplazamiento)
        return aplazamiento

    def approve(self, aplazamiento_id: int, aprobador_id: str) -> Aplazamiento:
        aplazamiento = self.db.query(Aplazamiento).get(aplazamiento_id)
        if not aplazamiento:
            raise ValueError("Aplazamiento no encontrado")
        if aplazamiento.estado != EstadoAplazamiento.pendiente:
            raise ValueError("Este aplazamiento ya fue resuelto")

        aplazamiento.estado = EstadoAplazamiento.aprobado
        aplazamiento.aprobador_id = aprobador_id
        aplazamiento.resolved_at = datetime.utcnow()

        project = self.db.query(Project).get(aplazamiento.project_id)
        project.fecha_finalizacion = aplazamiento.fecha_finalizacion_nueva
        project.fecha_justificacion = aplazamiento.fecha_justificacion_nueva
        project.ampliado = True

        self.db.commit()
        self.db.refresh(aplazamiento)
        return aplazamiento

    def reject(
        self, aplazamiento_id: int, aprobador_id: str, motivo_rechazo: str
    ) -> Aplazamiento:
        aplazamiento = self.db.query(Aplazamiento).get(aplazamiento_id)
        if not aplazamiento:
            raise ValueError("Aplazamiento no encontrado")
        if aplazamiento.estado != EstadoAplazamiento.pendiente:
            raise ValueError("Este aplazamiento ya fue resuelto")

        aplazamiento.estado = EstadoAplazamiento.rechazado
        aplazamiento.aprobador_id = aprobador_id
        aplazamiento.motivo_rechazo = motivo_rechazo
        aplazamiento.resolved_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(aplazamiento)
        return aplazamiento
