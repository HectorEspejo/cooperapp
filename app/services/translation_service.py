import hashlib
import json
import logging
import time
import threading
import httpx
from sqlalchemy.orm import Session
from app.models.translation_cache import TranslationCache
from app.config import get_settings
from app.database import SessionLocal

logger = logging.getLogger(__name__)

TARGET_LANGUAGES = ("fr", "en")

LANGUAGE_NAMES = {
    "fr": "frances",
    "en": "ingles",
}

TRANSLATABLE_FIELDS = {
    "project": ("titulo", "sector", "pais"),
    "logical_framework": ("objetivo_general",),
    "specific_objective": ("descripcion",),
    "result": ("descripcion",),
    "activity": ("descripcion",),
    "indicator": ("descripcion", "unidad_medida", "fuente_verificacion"),
    "document": ("descripcion",),
}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _retry_pending_in_background(pending_items: list[dict]):
    """Reintenta traducciones fallidas en un thread aparte."""
    db = SessionLocal()
    try:
        svc = TranslationService(db)
        for item in pending_items:
            svc.translate_entity(item["entity_type"], item["entity_id"], item["fields"])
    finally:
        db.close()


class TranslationService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def translate_entity(
        self, entity_type: str, entity_id: int, fields_data: dict[str, str]
    ) -> None:
        if not self.settings.openrouter_api_key:
            return

        # Filter out empty/None fields
        fields_data = {k: v for k, v in fields_data.items() if v}
        if not fields_data:
            return

        for lang in TARGET_LANGUAGES:
            pending = {}
            for field_name, text in fields_data.items():
                source_hash = _hash(text)

                # Check if cached with same hash
                existing = (
                    self.db.query(TranslationCache)
                    .filter_by(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        field_name=field_name,
                        language=lang,
                    )
                    .first()
                )
                if existing and existing.source_hash == source_hash:
                    continue

                # Check if another entity has the same hash (reuse translation)
                reusable = (
                    self.db.query(TranslationCache)
                    .filter_by(
                        field_name=field_name,
                        language=lang,
                        source_hash=source_hash,
                    )
                    .first()
                )
                if reusable:
                    if existing:
                        existing.translated_text = reusable.translated_text
                        existing.source_hash = source_hash
                    else:
                        self.db.add(
                            TranslationCache(
                                entity_type=entity_type,
                                entity_id=entity_id,
                                field_name=field_name,
                                language=lang,
                                translated_text=reusable.translated_text,
                                source_hash=source_hash,
                            )
                        )
                    self.db.commit()
                    continue

                pending[field_name] = text

            if not pending:
                continue

            # Call OpenRouter for all pending fields at once
            translated = self._call_openrouter(pending, lang)
            if not translated:
                continue

            for field_name, translated_text in translated.items():
                source_hash = _hash(fields_data[field_name])
                existing = (
                    self.db.query(TranslationCache)
                    .filter_by(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        field_name=field_name,
                        language=lang,
                    )
                    .first()
                )
                if existing:
                    existing.translated_text = translated_text
                    existing.source_hash = source_hash
                else:
                    self.db.add(
                        TranslationCache(
                            entity_type=entity_type,
                            entity_id=entity_id,
                            field_name=field_name,
                            language=lang,
                            translated_text=translated_text,
                            source_hash=source_hash,
                        )
                    )
            self.db.commit()

    def translate_on_demand(
        self, entity_type: str, entity_id: int, field_name: str,
        original: str, language: str,
    ) -> str | None:
        """Intenta traducir un campo individual con timeout corto.
        Retorna la traduccion o None si falla."""
        if not self.settings.openrouter_api_key:
            return None

        fields = {field_name: original}
        translated = self._call_openrouter(fields, language, max_retries=1, timeout=10.0)
        if not translated or field_name not in translated:
            return None

        translated_text = translated[field_name]
        source_hash = _hash(original)

        # Guardar en cache
        existing = (
            self.db.query(TranslationCache)
            .filter_by(
                entity_type=entity_type,
                entity_id=entity_id,
                field_name=field_name,
                language=language,
            )
            .first()
        )
        if existing:
            existing.translated_text = translated_text
            existing.source_hash = source_hash
        else:
            self.db.add(
                TranslationCache(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    field_name=field_name,
                    language=language,
                    translated_text=translated_text,
                    source_hash=source_hash,
                )
            )
        self.db.commit()
        return translated_text

    def _call_openrouter(
        self, fields: dict[str, str], target_lang: str,
        max_retries: int = 3, timeout: float = 30.0,
    ) -> dict[str, str] | None:
        lang_name = LANGUAGE_NAMES[target_lang]
        prompt = (
            f"Traduce los siguientes textos del espanol al {lang_name}. "
            f"Responde SOLO con un JSON valido con las mismas claves. "
            f"No agregues explicaciones.\n\n"
            f"{json.dumps(fields, ensure_ascii=False)}"
        )

        for attempt in range(max_retries):
            try:
                response = httpx.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.settings.openrouter_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                    },
                    timeout=timeout,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]

                # Extract JSON from response (handle markdown code blocks)
                content = content.strip()
                if content.startswith("```"):
                    lines = content.split("\n")
                    content = "\n".join(lines[1:-1]).strip()

                return json.loads(content)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        "Rate limited (429) translating to %s, retry %d/%d in %ds",
                        target_lang, attempt + 1, max_retries, wait,
                    )
                    time.sleep(wait)
                    continue
                logger.exception(
                    "Error calling OpenRouter for translation to %s", target_lang
                )
                return None
            except Exception:
                logger.exception(
                    "Error calling OpenRouter for translation to %s", target_lang
                )
                return None
        return None

    def get_translated_text(
        self,
        entity_type: str,
        entity_id: int,
        field_name: str,
        original: str,
        language: str,
    ) -> str:
        if language == "es" or not original:
            return original or ""

        cached = (
            self.db.query(TranslationCache)
            .filter_by(
                entity_type=entity_type,
                entity_id=entity_id,
                field_name=field_name,
                language=language,
            )
            .first()
        )
        if cached:
            return cached.translated_text
        return original or ""
