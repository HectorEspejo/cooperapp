from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CounterpartSession(Base):
    __tablename__ = "counterpart_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"))
    session_token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.utcnow() + timedelta(hours=8)
    )
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    language: Mapped[str] = mapped_column(String(5), default="es")

    project = relationship("Project")

    @property
    def is_valid(self) -> bool:
        now = datetime.utcnow()
        if not self.activo:
            return False
        if now > self.expires_at:
            return False
        # 2h inactivity timeout
        if (now - self.last_activity).total_seconds() > 7200:
            return False
        return True

    @property
    def tiempo_restante_minutos(self) -> int:
        now = datetime.utcnow()
        abs_remaining = (self.expires_at - now).total_seconds() / 60
        inactivity_remaining = (7200 - (now - self.last_activity).total_seconds()) / 60
        return max(0, int(min(abs_remaining, inactivity_remaining)))
