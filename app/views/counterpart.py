import os
import threading
from datetime import date
from fastapi import APIRouter, BackgroundTasks, Depends, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models.counterpart_session import CounterpartSession
from app.auth.dependencies import get_current_counterpart
from app.services.project_service import ProjectService
from app.services.logical_framework_service import LogicalFrameworkService
from app.services.document_service import DocumentService
from app.services.translation_service import TranslationService, _retry_pending_in_background
from app.models.logical_framework import EstadoActividad
from app.models.document import CategoriaDocumento, CATEGORIA_NOMBRES
from app.schemas.logical_framework import ActivityUpdate
from app.schemas.document import DocumentCreate
from app.services.audit_service import AuditService
from app.models.audit_log import ActorType, AccionAuditoria
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


def _trigger_translation_bg(entity_type: str, entity_id: int, fields_data: dict):
    db = SessionLocal()
    try:
        TranslationService(db).translate_entity(entity_type, entity_id, fields_data)
    finally:
        db.close()


def _validate_counterpart_project(session: CounterpartSession, project_id: int, project_service: ProjectService):
    """Valida acceso de contraparte al proyecto y lo devuelve."""
    if session.project_id != project_id:
        raise HTTPException(status_code=403, detail="Sin acceso a este proyecto")
    project = project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return project


def _ml_context(request, project, framework, summary, lang, t, tc):
    """Contexto comun para renderizar marco logico en modo contraparte."""
    return {
        "request": request,
        "project": project,
        "framework": framework,
        "summary": summary,
        "estados_actividad": list(EstadoActividad),
        "readonly": True,
        "is_counterpart": True,
        "lang": lang,
        "t": t,
        "tc": tc,
    }


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
    ctx = _ml_context(request, project, framework, summary, lang, t, tc)
    response = templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html", ctx,
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
            "is_counterpart": True,
            "lang": lang,
            "t": t,
            "tc": tc,
        },
    )
    _flush_pending_retries(tc)
    return response


# ======================== Counterpart Activity Endpoints ========================


@router.post("/contraparte/{project_id}/activities/{activity_id}/status", response_class=HTMLResponse)
def counterpart_update_activity_status(
    request: Request,
    project_id: int,
    activity_id: int,
    session: CounterpartSession = Depends(get_current_counterpart),
    estado: EstadoActividad = Form(...),
    project_service: ProjectService = Depends(get_project_service),
    lf_service: LogicalFrameworkService = Depends(get_lf_service),
    db: Session = Depends(get_db),
):
    """Actualizar estado de actividad desde portal contraparte."""
    project = _validate_counterpart_project(session, project_id, project_service)

    activity = lf_service.get_activity(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    data = ActivityUpdate(estado=estado)
    lf_service.update_activity(activity_id, data)

    # Audit log
    audit = AuditService(db)
    audit.log(
        actor_type=ActorType.counterpart,
        actor_id=str(session.id),
        actor_email=None,
        actor_label=f"Contraparte ({project.codigo_contable})",
        accion=AccionAuditoria.status_change,
        recurso="activity",
        recurso_id=str(activity_id),
        detalle={"estado": estado.value},
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    lang = session.language or "es"
    t = get_translator(lang)
    tc = _build_content_translator(db, lang)
    framework = lf_service.get_framework_by_project(project_id)
    summary = lf_service.get_framework_summary(project_id)
    ctx = _ml_context(request, project, framework, summary, lang, t, tc)
    response = templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html", ctx,
    )
    _flush_pending_retries(tc)
    return response


@router.get("/contraparte/{project_id}/marco-logico/activity-form", response_class=HTMLResponse)
def counterpart_get_activity_form(
    request: Request,
    project_id: int,
    activity_id: int,
    session: CounterpartSession = Depends(get_current_counterpart),
    project_service: ProjectService = Depends(get_project_service),
    lf_service: LogicalFrameworkService = Depends(get_lf_service),
):
    """Formulario de edicion de actividad para contraparte."""
    _validate_counterpart_project(session, project_id, project_service)

    activity = lf_service.get_activity(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    lang = session.language or "es"
    t = get_translator(lang)

    return templates.TemplateResponse(
        "partials/projects/marco_logico_activity_form.html",
        {
            "request": request,
            "project_id": project_id,
            "result_id": activity.result_id,
            "activity": activity,
            "mode": "edit",
            "next_numero": activity.numero,
            "estados_actividad": list(EstadoActividad),
            "is_counterpart": True,
            "t": t,
            "lang": lang,
        },
    )


@router.put("/contraparte/{project_id}/activities/{activity_id}", response_class=HTMLResponse)
async def counterpart_update_activity(
    request: Request,
    project_id: int,
    activity_id: int,
    background_tasks: BackgroundTasks,
    session: CounterpartSession = Depends(get_current_counterpart),
    project_service: ProjectService = Depends(get_project_service),
    lf_service: LogicalFrameworkService = Depends(get_lf_service),
    db: Session = Depends(get_db),
):
    """Actualizar actividad desde portal contraparte."""
    project = _validate_counterpart_project(session, project_id, project_service)

    activity = lf_service.get_activity(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    form_data = await request.form()
    data = ActivityUpdate()
    if form_data.get("numero"):
        data.numero = form_data.get("numero")
    if form_data.get("descripcion"):
        data.descripcion = form_data.get("descripcion")
    if form_data.get("fecha_inicio_prevista"):
        data.fecha_inicio_prevista = date.fromisoformat(form_data.get("fecha_inicio_prevista"))
    if form_data.get("fecha_fin_prevista"):
        data.fecha_fin_prevista = date.fromisoformat(form_data.get("fecha_fin_prevista"))
    if form_data.get("fecha_inicio_real"):
        data.fecha_inicio_real = date.fromisoformat(form_data.get("fecha_inicio_real"))
    if form_data.get("fecha_fin_real"):
        data.fecha_fin_real = date.fromisoformat(form_data.get("fecha_fin_real"))
    if form_data.get("estado"):
        data.estado = EstadoActividad(form_data.get("estado"))

    lf_service.update_activity(activity_id, data)

    # Audit log
    audit = AuditService(db)
    audit.log(
        actor_type=ActorType.counterpart,
        actor_id=str(session.id),
        actor_email=None,
        actor_label=f"Contraparte ({project.codigo_contable})",
        accion=AccionAuditoria.update,
        recurso="activity",
        recurso_id=str(activity_id),
        detalle=None,
        ip_address=request.client.host if request.client else None,
        project_id=project_id,
    )

    if data.descripcion:
        background_tasks.add_task(
            _trigger_translation_bg, "activity", activity_id,
            {"descripcion": data.descripcion},
        )

    lang = session.language or "es"
    t = get_translator(lang)
    tc = _build_content_translator(db, lang)
    framework = lf_service.get_framework_by_project(project_id)
    summary = lf_service.get_framework_summary(project_id)
    ctx = _ml_context(request, project, framework, summary, lang, t, tc)
    response = templates.TemplateResponse(
        "partials/projects/marco_logico_tab.html", ctx,
    )
    _flush_pending_retries(tc)
    return response


# ======================== Counterpart Document Endpoints ========================


@router.post("/contraparte/{project_id}/documents", response_class=HTMLResponse)
async def counterpart_upload_document(
    request: Request,
    project_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    categoria: CategoriaDocumento = Form(...),
    descripcion: str | None = Form(None),
    session: CounterpartSession = Depends(get_current_counterpart),
    project_service: ProjectService = Depends(get_project_service),
    doc_service: DocumentService = Depends(get_doc_service),
    db: Session = Depends(get_db),
):
    """Subir documento desde portal contraparte."""
    project = _validate_counterpart_project(session, project_id, project_service)

    try:
        data = DocumentCreate(categoria=categoria, descripcion=descripcion)
        document = doc_service.create_document(project_id, file, data)

        # Audit log
        audit = AuditService(db)
        audit.log(
            actor_type=ActorType.counterpart,
            actor_id=str(session.id),
            actor_email=None,
            actor_label=f"Contraparte ({project.codigo_contable})",
            accion=AccionAuditoria.upload,
            recurso="document",
            recurso_id=str(document.id),
            detalle={"filename": file.filename, "categoria": categoria.value},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if document and descripcion:
        background_tasks.add_task(
            _trigger_translation_bg, "document", document.id,
            {"descripcion": descripcion},
        )

    lang = session.language or "es"
    t = get_translator(lang)
    tc = _build_content_translator(db, lang)
    cat_nombres = CATEGORIA_NOMBRES_I18N.get(lang, CATEGORIA_NOMBRES)

    documents = doc_service.get_project_documents(project_id)
    summary = doc_service.get_document_summary(project_id)

    response = templates.TemplateResponse(
        "partials/projects/documents_tab.html",
        {
            "request": request,
            "project": project,
            "documents": documents,
            "summary": summary,
            "categorias": CategoriaDocumento,
            "categoria_nombres": cat_nombres,
            "is_counterpart": True,
            "lang": lang,
            "t": t,
            "tc": tc,
        },
    )
    _flush_pending_retries(tc)
    return response


@router.get("/contraparte/{project_id}/documents/{document_id}/download")
def counterpart_download_document(
    project_id: int,
    document_id: int,
    session: CounterpartSession = Depends(get_current_counterpart),
    project_service: ProjectService = Depends(get_project_service),
    doc_service: DocumentService = Depends(get_doc_service),
):
    """Descargar documento desde portal contraparte."""
    _validate_counterpart_project(session, project_id, project_service)

    document = doc_service.get_document_by_id(document_id)
    if not document or document.project_id != project_id:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    if not os.path.exists(document.file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado en disco")

    return FileResponse(
        path=document.file_path,
        filename=document.original_filename,
        media_type=document.mime_type or "application/octet-stream",
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
