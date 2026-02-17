import threading
from fastapi import APIRouter, BackgroundTasks, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.counterpart_session import CounterpartSession
from app.auth.dependencies import get_current_counterpart
from app.services.project_service import ProjectService
from app.services.logical_framework_service import LogicalFrameworkService
from app.services.document_service import DocumentService
from app.services.translation_service import TranslationService, _retry_pending_in_background
from app.models.logical_framework import EstadoActividad
from app.models.document import CategoriaDocumento, CATEGORIA_NOMBRES
from app.i18n import get_translator

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

CATEGORIA_NOMBRES_I18N = {
    "fr": {
        "factura": "Facture",
        "comprobante": "Justificatif",
        "fuente_verificacion": "Source de Verification",
        "informe": "Rapport",
        "contrato": "Contrat",
        "convenio": "Convention",
        "acta": "Proces-verbal",
        "listado_asistencia": "Liste de Presence",
        "foto": "Photo",
        "otro": "Autre",
    },
    "en": {
        "factura": "Invoice",
        "comprobante": "Receipt",
        "fuente_verificacion": "Verification Source",
        "informe": "Report",
        "contrato": "Contract",
        "convenio": "Agreement",
        "acta": "Minutes",
        "listado_asistencia": "Attendance List",
        "foto": "Photo",
        "otro": "Other",
    },
}


def _build_content_translator(db: Session, language: str):
    """Construye tc() con traduccion lazy on-demand + retry en background.

    - Si hay cache: devuelve la traduccion cacheada.
    - Si no hay cache: intenta traducir on-demand (timeout corto 10s).
    - Si on-demand falla: devuelve el original y acumula el campo en
      `pending_retries` para reintentarlo en un thread background.
    """
    if language == "es":
        def tc(entity_type, entity_id, field_name, original_text):
            return original_text or ""
        tc.pending_retries = []
        return tc

    svc = TranslationService(db)
    cache = {}
    pending_retries = []

    def tc(entity_type, entity_id, field_name, original_text):
        if not original_text:
            return ""
        key = (entity_type, entity_id, field_name)
        if key in cache:
            return cache[key]

        # Buscar en DB
        result = svc.get_translated_text(
            entity_type, entity_id, field_name, original_text, language
        )
        if result != original_text:
            # Hay traduccion en cache
            cache[key] = result
            return result

        # No hay cache: intentar on-demand
        translated = svc.translate_on_demand(
            entity_type, entity_id, field_name, original_text, language
        )
        if translated:
            cache[key] = translated
            return translated

        # Fallo on-demand: acumular para retry background
        pending_retries.append({
            "entity_type": entity_type,
            "entity_id": entity_id,
            "fields": {field_name: original_text},
        })
        cache[key] = original_text
        return original_text

    tc.pending_retries = pending_retries
    return tc


def _flush_pending_retries(tc):
    """Lanza un thread para reintentar las traducciones que fallaron on-demand."""
    pending = getattr(tc, "pending_retries", [])
    if not pending:
        return
    # Agrupar por entidad para hacer menos llamadas API
    grouped = {}
    for item in pending:
        key = (item["entity_type"], item["entity_id"])
        if key not in grouped:
            grouped[key] = {"entity_type": item["entity_type"], "entity_id": item["entity_id"], "fields": {}}
        grouped[key]["fields"].update(item["fields"])

    thread = threading.Thread(
        target=_retry_pending_in_background,
        args=(list(grouped.values()),),
        daemon=True,
    )
    thread.start()


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


def get_lf_service(db: Session = Depends(get_db)) -> LogicalFrameworkService:
    return LogicalFrameworkService(db)


def get_doc_service(db: Session = Depends(get_db)) -> DocumentService:
    return DocumentService(db)


@router.get("/contraparte/{project_id}", response_class=HTMLResponse)
def counterpart_portal(
    request: Request,
    project_id: int,
    session: CounterpartSession = Depends(get_current_counterpart),
    project_service: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
):
    if session.project_id != project_id:
        raise HTTPException(status_code=403, detail="Sin acceso a este proyecto")

    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    lang = session.language or "es"
    t = get_translator(lang)
    tc = _build_content_translator(db, lang)
    response = templates.TemplateResponse(
        "pages/counterpart/portal.html",
        {
            "request": request,
            "project": project,
            "session": session,
            "lang": lang,
            "t": t,
            "tc": tc,
        },
    )
    _flush_pending_retries(tc)
    return response


@router.get("/contraparte/{project_id}/marco-logico", response_class=HTMLResponse)
def counterpart_marco_logico(
    request: Request,
    project_id: int,
    session: CounterpartSession = Depends(get_current_counterpart),
    project_service: ProjectService = Depends(get_project_service),
    lf_service: LogicalFrameworkService = Depends(get_lf_service),
    db: Session = Depends(get_db),
):
    if session.project_id != project_id:
        raise HTTPException(status_code=403, detail="Sin acceso a este proyecto")

    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    framework = lf_service.get_framework_by_project(project_id)
    summary = lf_service.get_framework_summary(project_id)

    lang = session.language or "es"
    t = get_translator(lang)
    tc = _build_content_translator(db, lang)
    response = templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html",
        {
            "request": request,
            "project": project,
            "framework": framework,
            "summary": summary,
            "estados_actividad": list(EstadoActividad),
            "readonly": True,
            "lang": lang,
            "t": t,
            "tc": tc,
        },
    )
    _flush_pending_retries(tc)
    return response


@router.get("/contraparte/{project_id}/documentos", response_class=HTMLResponse)
def counterpart_documents(
    request: Request,
    project_id: int,
    session: CounterpartSession = Depends(get_current_counterpart),
    project_service: ProjectService = Depends(get_project_service),
    doc_service: DocumentService = Depends(get_doc_service),
    db: Session = Depends(get_db),
):
    if session.project_id != project_id:
        raise HTTPException(status_code=403, detail="Sin acceso a este proyecto")

    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    documents = doc_service.get_project_documents(project_id)
    summary = doc_service.get_document_summary(project_id)

    lang = session.language or "es"
    t = get_translator(lang)
    tc = _build_content_translator(db, lang)
    cat_nombres = CATEGORIA_NOMBRES_I18N.get(lang, CATEGORIA_NOMBRES)
    response = templates.TemplateResponse(
        "partials/projects/documents_tab.html",
        {
            "request": request,
            "project": project,
            "documents": documents,
            "summary": summary,
            "categorias": CategoriaDocumento,
            "categoria_nombres": cat_nombres,
            "readonly": True,
            "lang": lang,
            "t": t,
            "tc": tc,
        },
    )
    _flush_pending_retries(tc)
    return response


@router.get("/contraparte/session-timer", response_class=HTMLResponse)
def session_timer(
    request: Request,
    session: CounterpartSession = Depends(get_current_counterpart),
):
    lang = session.language or "es"
    t = get_translator(lang)
    return templates.TemplateResponse(
        "partials/auth/session_timer.html",
        {
            "request": request,
            "session": session,
            "lang": lang,
            "t": t,
        },
    )
