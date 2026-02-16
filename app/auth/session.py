from datetime import datetime, timedelta
from uuid import uuid4
from fastapi import Request, Response
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.counterpart_session import CounterpartSession
from app.models.project import EstadoProyecto


def create_internal_session(request: Request, user: User):
    request.session["user_id"] = user.id


def destroy_internal_session(request: Request):
    request.session.clear()


def create_counterpart_session(
    db: Session, project_id: int, ip_address: str | None, user_agent: str | None,
    language: str = "es",
) -> CounterpartSession:
    token = str(uuid4())
    session = CounterpartSession(
        project_id=project_id,
        session_token=token,
        ip_address=ip_address,
        user_agent=user_agent,
        language=language,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def validate_project_code(db: Session, code: str):
    from app.models.project import Project
    project = db.query(Project).filter(Project.codigo_contable == code).first()
    if not project:
        return None
    if project.estado not in (EstadoProyecto.ejecucion, EstadoProyecto.justificacion):
        return None
    return project


def set_counterpart_cookie(response: Response, token: str):
    response.set_cookie(
        key="counterpart_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=8 * 3600,
    )


def clear_counterpart_cookie(response: Response):
    response.delete_cookie(key="counterpart_token")
