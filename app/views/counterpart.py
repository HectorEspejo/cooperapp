from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.counterpart_session import CounterpartSession
from app.auth.dependencies import get_current_counterpart
from app.services.project_service import ProjectService
from app.services.logical_framework_service import LogicalFrameworkService
from app.services.document_service import DocumentService
from app.services.translation_service import TranslationService
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
    if language == "es":
        def tc(entity_type, entity_id, field_name, original_text):
            return original_text or ""
        return tc

    svc = TranslationService(db)
    cache = {}

    def tc(entity_type, entity_id, field_name, original_text):
        if not original_text:
            return ""
        key = (entity_type, entity_id, field_name)
        if key not in cache:
            cache[key] = svc.get_translated_text(
                entity_type, entity_id, field_name, original_text, language
            )
        return cache[key]

    return tc


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
    return templates.TemplateResponse(
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
    return templates.TemplateResponse(
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
    return templates.TemplateResponse(
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
