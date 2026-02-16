from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class TranslationCache(Base):
    __tablename__ = "translation_cache"
    __table_args__ = (
        UniqueConstraint(
            "entity_type", "entity_id", "field_name", "language",
            name="uq_translation_entity_field_lang"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    field_name: Mapped[str] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(5))
    translated_text: Mapped[str] = mapped_column(Text)
    source_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<TranslationCache {self.entity_type}:{self.entity_id}.{self.field_name} [{self.language}]>"
