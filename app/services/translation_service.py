import hashlib
import json
import logging
import httpx
from sqlalchemy.orm import Session
from app.models.translation_cache import TranslationCache
from app.config import get_settings

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

    def _call_openrouter(
        self, fields: dict[str, str], target_lang: str
    ) -> dict[str, str] | None:
        lang_name = LANGUAGE_NAMES[target_lang]
        prompt = (
            f"Traduce los siguientes textos del espanol al {lang_name}. "
            f"Responde SOLO con un JSON valido con las mismas claves. "
            f"No agregues explicaciones.\n\n"
            f"{json.dumps(fields, ensure_ascii=False)}"
        )

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
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Extract JSON from response (handle markdown code blocks)
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                # Remove first and last lines (```json and ```)
                content = "\n".join(lines[1:-1]).strip()

            return json.loads(content)
        except Exception:
            logger.exception(
                "Error calling OpenRouter for translation to %s", target_lang
            )
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
