import os
import threading
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, BackgroundTasks, Depends, Request, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models.counterpart_session import CounterpartSession
from app.auth.dependencies import get_current_counterpart
from app.services.project_service import ProjectService
from app.services.logical_framework_service import LogicalFrameworkService
from app.services.document_service import DocumentService
from app.services.expense_service import ExpenseService
from app.services.budget_service import BudgetService
from app.services.translation_service import TranslationService, _retry_pending_in_background
from app.models.logical_framework import EstadoActividad, Indicator, Activity
from app.models.expense import UbicacionGasto, EstadoGasto
from app.models.document import CategoriaDocumento, CATEGORIA_NOMBRES, TipoFuenteVerificacion, TIPO_FUENTE_NOMBRES
from app.models.funding import TipoFuente
from app.schemas.logical_framework import ActivityUpdate
from app.schemas.expense import ExpenseCreate, ExpenseFilters
from app.schemas.document import DocumentCreate, VerificationSourceCreate
from app.services.verification_source_service import VerificationSourceService
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


TIPO_FUENTE_NOMBRES_I18N = {
    "fr": {
        "foto": "Photo", "acta": "Proces-verbal", "listado_asistencia": "Liste de Presence",
        "informe": "Rapport", "certificado": "Certificat", "contrato": "Contrat", "otro": "Autre",
    },
    "en": {
        "foto": "Photo", "acta": "Minutes", "listado_asistencia": "Attendance List",
        "informe": "Report", "certificado": "Certificate", "contrato": "Contract", "otro": "Other",
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


def get_expense_service(db: Session = Depends(get_db)) -> ExpenseService:
    return ExpenseService(db)


def get_budget_service(db: Session = Depends(get_db)) -> BudgetService:
    return BudgetService(db)


def get_verification_service(db: Session = Depends(get_db)) -> VerificationSourceService:
    return VerificationSourceService(db)


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


# ======================== Counterpart Budget Endpoints ========================


@router.get("/contraparte/{project_id}/presupuesto", response_class=HTMLResponse)
def counterpart_budget(
    request: Request,
    project_id: int,
    session: CounterpartSession = Depends(get_current_counterpart),
    project_service: ProjectService = Depends(get_project_service),
    budget_service: BudgetService = Depends(get_budget_service),
    db: Session = Depends(get_db),
):
    """Tab de presupuesto readonly para contraparte."""
    project = _validate_counterpart_project(session, project_id, project_service)

    budget_summary = budget_service.get_project_budget_summary(project_id)
    funding_sources = budget_service.get_project_funding_sources(project_id)
    funding_summary = budget_service.get_funding_summary(project_id)

    lang = session.language or "es"
    t = get_translator(lang)

    return templates.TemplateResponse(
        "partials/projects/budget_tab.html",
        {
            "request": request,
            "project": project,
            "budget": budget_summary,
            "funding_sources": funding_sources,
            "funding_summary": funding_summary,
            "is_counterpart": True,
            "lang": lang,
            "t": t,
        },
    )


# ======================== Counterpart Expense Endpoints ========================


@router.get("/contraparte/{project_id}/gastos", response_class=HTMLResponse)
def counterpart_expenses(
    request: Request,
    project_id: int,
    budget_line_id: int | None = Query(None),
    estado: str | None = Query(None),
    ubicacion: str | None = Query(None),
    fecha_desde: date | None = Query(None),
    fecha_hasta: date | None = Query(None),
    funding_source_id: int | None = Query(None),
    session: CounterpartSession = Depends(get_current_counterpart),
    project_service: ProjectService = Depends(get_project_service),
    expense_service: ExpenseService = Depends(get_expense_service),
    budget_service: BudgetService = Depends(get_budget_service),
    db: Session = Depends(get_db),
):
    """Tab de gastos para contraparte."""
    project = _validate_counterpart_project(session, project_id, project_service)

    filters = ExpenseFilters(
        budget_line_id=budget_line_id,
        estado=EstadoGasto(estado) if estado else None,
        ubicacion=UbicacionGasto(ubicacion) if ubicacion else None,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        funding_source_id=funding_source_id,
    )

    expenses = expense_service.get_project_expenses(project_id, filters)
    summary = expense_service.get_expense_summary(project_id)
    budget_lines = expense_service.get_budget_lines_with_balance(project_id)
    funding_sources = budget_service.get_project_funding_sources(project_id)

    funder = budget_service.get_funder_for_financiador(project.financiador)
    funder_code = funder.code if funder else None

    lang = session.language or "es"
    t = get_translator(lang)

    return templates.TemplateResponse(
        "partials/projects/expenses_tab.html",
        {
            "request": request,
            "project": project,
            "expenses": expenses,
            "summary": summary,
            "budget_lines": budget_lines,
            "funding_sources": funding_sources,
            "funder_code": funder_code,
            "is_counterpart": True,
            "lang": lang,
            "t": t,
        },
    )


@router.get("/contraparte/{project_id}/gastos/nuevo", response_class=HTMLResponse)
def counterpart_new_expense_form(
    request: Request,
    project_id: int,
    session: CounterpartSession = Depends(get_current_counterpart),
    project_service: ProjectService = Depends(get_project_service),
    expense_service: ExpenseService = Depends(get_expense_service),
    budget_service: BudgetService = Depends(get_budget_service),
):
    """Formulario de nuevo gasto para contraparte."""
    project = _validate_counterpart_project(session, project_id, project_service)

    funding_source = budget_service.get_counterpart_funding_source(project_id)
    if not funding_source:
        raise HTTPException(status_code=400, detail="No hay fuente de financiacion tipo contraparte configurada")

    budget_lines = expense_service.get_budget_lines_with_balance(project_id)

    funder = budget_service.get_funder_for_financiador(project.financiador)
    funder_code = funder.code if funder else None

    lang = session.language or "es"
    t = get_translator(lang)

    return templates.TemplateResponse(
        "partials/projects/counterpart_expense_form.html",
        {
            "request": request,
            "project": project,
            "funding_source": funding_source,
            "budget_lines": budget_lines,
            "funder_code": funder_code,
            "lang": lang,
            "t": t,
        },
    )


@router.post("/contraparte/{project_id}/gastos", response_class=HTMLResponse)
async def counterpart_create_expense(
    request: Request,
    project_id: int,
    session: CounterpartSession = Depends(get_current_counterpart),
    project_service: ProjectService = Depends(get_project_service),
    expense_service: ExpenseService = Depends(get_expense_service),
    budget_service: BudgetService = Depends(get_budget_service),
    db: Session = Depends(get_db),
):
    """Crear gasto desde portal contraparte y enviarlo directamente a revision."""
    project = _validate_counterpart_project(session, project_id, project_service)

    form_data = await request.form()

    try:
        funding_source_id = int(form_data.get("funding_source_id"))
        source = budget_service.get_funding_source_by_id(funding_source_id)
        if not source or source.tipo != TipoFuente.contraparte:
            raise HTTPException(status_code=400, detail="Fuente de financiacion invalida")

        data = ExpenseCreate(
            budget_line_id=int(form_data.get("budget_line_id")),
            fecha_factura=date.fromisoformat(form_data.get("fecha_factura")),
            concepto=form_data.get("concepto"),
            expedidor=form_data.get("expedidor"),
            persona=form_data.get("persona") or None,
            cantidad_original=Decimal(str(form_data.get("cantidad_original", "0")).replace(",", ".")),
            moneda_original=form_data.get("moneda_original", "EUR"),
            tipo_cambio=Decimal(str(form_data.get("tipo_cambio")).replace(",", ".")) if form_data.get("tipo_cambio") else None,
            cantidad_euros=Decimal(str(form_data.get("cantidad_euros", "0")).replace(",", ".")),
            porcentaje=Decimal(str(form_data.get("porcentaje", "100")).replace(",", ".")),
            financiado_por=source.nombre,
            ubicacion=UbicacionGasto(form_data.get("ubicacion")),
            observaciones=form_data.get("observaciones") or None,
            funding_source_id=funding_source_id,
        )

        expense = expense_service.create_expense(project_id, data)
        # Enviar directamente a revision
        expense_service.submit_for_review(expense.id)

        # Audit log
        audit = AuditService(db)
        audit.log(
            actor_type=ActorType.counterpart,
            actor_id=str(session.id),
            actor_email=None,
            actor_label=f"Contraparte ({project.codigo_contable})",
            accion=AccionAuditoria.create,
            recurso="expense",
            recurso_id=str(expense.id),
            detalle={"concepto": data.concepto, "cantidad_euros": str(data.cantidad_euros)},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Devolver tab actualizado
    expenses = expense_service.get_project_expenses(project_id)
    summary = expense_service.get_expense_summary(project_id)
    budget_lines = expense_service.get_budget_lines_with_balance(project_id)
    funding_sources = budget_service.get_project_funding_sources(project_id)

    funder = budget_service.get_funder_for_financiador(project.financiador)
    funder_code = funder.code if funder else None

    lang = session.language or "es"
    t = get_translator(lang)

    return templates.TemplateResponse(
        "partials/projects/expenses_tab.html",
        {
            "request": request,
            "project": project,
            "expenses": expenses,
            "summary": summary,
            "budget_lines": budget_lines,
            "funding_sources": funding_sources,
            "funder_code": funder_code,
            "is_counterpart": True,
            "lang": lang,
            "t": t,
        },
    )


@router.get("/contraparte/{project_id}/gastos/{expense_id}/upload-modal", response_class=HTMLResponse)
def counterpart_upload_modal(
    request: Request,
    project_id: int,
    expense_id: int,
    session: CounterpartSession = Depends(get_current_counterpart),
    project_service: ProjectService = Depends(get_project_service),
    expense_service: ExpenseService = Depends(get_expense_service),
):
    """Modal de subida de justificante para contraparte."""
    project = _validate_counterpart_project(session, project_id, project_service)

    expense = expense_service.get_expense_by_id(expense_id)
    if not expense or expense.project_id != project_id:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")

    # Solo permitir subir si esta pendiente_revision y es fuente contraparte
    if expense.estado != EstadoGasto.pendiente_revision:
        raise HTTPException(status_code=400, detail="Solo se puede subir justificante a gastos pendientes de revision")

    lang = session.language or "es"
    t = get_translator(lang)

    return templates.TemplateResponse(
        "partials/projects/counterpart_expense_upload.html",
        {
            "request": request,
            "project": project,
            "expense": expense,
            "lang": lang,
            "t": t,
        },
    )


@router.post("/contraparte/{project_id}/gastos/{expense_id}/upload", response_class=HTMLResponse)
async def counterpart_upload_document(
    request: Request,
    project_id: int,
    expense_id: int,
    file: UploadFile = File(...),
    session: CounterpartSession = Depends(get_current_counterpart),
    project_service: ProjectService = Depends(get_project_service),
    expense_service: ExpenseService = Depends(get_expense_service),
    budget_service: BudgetService = Depends(get_budget_service),
    doc_service: DocumentService = Depends(get_doc_service),
    db: Session = Depends(get_db),
):
    """Subir justificante desde portal contraparte."""
    project = _validate_counterpart_project(session, project_id, project_service)

    expense = expense_service.get_expense_by_id(expense_id)
    if not expense or expense.project_id != project_id:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")

    try:
        expense_service.save_document(expense_id, file)

        # Audit log
        audit = AuditService(db)
        audit.log(
            actor_type=ActorType.counterpart,
            actor_id=str(session.id),
            actor_email=None,
            actor_label=f"Contraparte ({project.codigo_contable})",
            accion=AccionAuditoria.upload,
            recurso="expense_document",
            recurso_id=str(expense_id),
            detalle={"filename": file.filename},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )

        # Also create entry in project documents
        await file.seek(0)
        budget_line = expense.budget_line
        concepto_short = expense.concepto[:50] if len(expense.concepto) > 50 else expense.concepto
        document_data = DocumentCreate(
            categoria=CategoriaDocumento.factura,
            descripcion=f"Factura - {budget_line.name} - {concepto_short}",
        )
        doc_service.create_document(project_id, file, document_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Devolver tab actualizado
    expenses = expense_service.get_project_expenses(project_id)
    summary = expense_service.get_expense_summary(project_id)
    budget_lines = expense_service.get_budget_lines_with_balance(project_id)
    funding_sources = budget_service.get_project_funding_sources(project_id)

    funder = budget_service.get_funder_for_financiador(project.financiador)
    funder_code = funder.code if funder else None

    lang = session.language or "es"
    t = get_translator(lang)

    return templates.TemplateResponse(
        "partials/projects/expenses_tab.html",
        {
            "request": request,
            "project": project,
            "expenses": expenses,
            "summary": summary,
            "budget_lines": budget_lines,
            "funding_sources": funding_sources,
            "funder_code": funder_code,
            "is_counterpart": True,
            "lang": lang,
            "t": t,
        },
    )


@router.get("/contraparte/{project_id}/gastos/{expense_id}/document")
def counterpart_expense_document(
    project_id: int,
    expense_id: int,
    session: CounterpartSession = Depends(get_current_counterpart),
    project_service: ProjectService = Depends(get_project_service),
    expense_service: ExpenseService = Depends(get_expense_service),
):
    """Descargar documento de gasto desde portal contraparte."""
    _validate_counterpart_project(session, project_id, project_service)

    expense = expense_service.get_expense_by_id(expense_id)
    if not expense or expense.project_id != project_id:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")

    if not expense.documento_path:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    if not os.path.exists(expense.documento_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    filename = os.path.basename(expense.documento_path)
    return FileResponse(expense.documento_path, filename=filename)


# ======================== Counterpart Verification Source Endpoints ========================


@router.get("/contraparte/{project_id}/indicators/{indicator_id}/verification-sources", response_class=HTMLResponse)
def counterpart_indicator_sources_modal(
    request: Request,
    project_id: int,
    indicator_id: int,
    session: CounterpartSession = Depends(get_current_counterpart),
    project_service: ProjectService = Depends(get_project_service),
    verification_service: VerificationSourceService = Depends(get_verification_service),
    db: Session = Depends(get_db),
):
    """Modal de fuentes de verificacion para indicador (contraparte)."""
    project = _validate_counterpart_project(session, project_id, project_service)

    indicator = db.get(Indicator, indicator_id)
    if not indicator or indicator.framework.project_id != project_id:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")

    lang = session.language or "es"
    t = get_translator(lang)
    tipo_nombres = TIPO_FUENTE_NOMBRES_I18N.get(lang, TIPO_FUENTE_NOMBRES)

    sources = verification_service.get_indicator_sources(indicator_id)
    summary = verification_service.get_indicator_summary(indicator_id)
    available_documents = verification_service.get_available_documents(project_id)

    return templates.TemplateResponse(
        "partials/projects/verification_sources_modal.html",
        {
            "request": request,
            "target_type": "indicator",
            "target_id": indicator_id,
            "target": indicator,
            "project_id": project_id,
            "sources": sources,
            "summary": summary,
            "available_documents": available_documents,
            "tipos": TipoFuenteVerificacion,
            "tipo_nombres": tipo_nombres,
            "is_counterpart": True,
            "t": t,
        },
    )


@router.get("/contraparte/{project_id}/activities/{activity_id}/verification-sources", response_class=HTMLResponse)
def counterpart_activity_sources_modal(
    request: Request,
    project_id: int,
    activity_id: int,
    session: CounterpartSession = Depends(get_current_counterpart),
    project_service: ProjectService = Depends(get_project_service),
    verification_service: VerificationSourceService = Depends(get_verification_service),
    db: Session = Depends(get_db),
):
    """Modal de fuentes de verificacion para actividad (contraparte)."""
    project = _validate_counterpart_project(session, project_id, project_service)

    activity = db.get(Activity, activity_id)
    if not activity or activity.result.objective.framework.project_id != project_id:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    lang = session.language or "es"
    t = get_translator(lang)
    tipo_nombres = TIPO_FUENTE_NOMBRES_I18N.get(lang, TIPO_FUENTE_NOMBRES)

    sources = verification_service.get_activity_sources(activity_id)
    summary = verification_service.get_activity_summary(activity_id)
    available_documents = verification_service.get_available_documents(project_id)

    return templates.TemplateResponse(
        "partials/projects/verification_sources_modal.html",
        {
            "request": request,
            "target_type": "activity",
            "target_id": activity_id,
            "target": activity,
            "project_id": project_id,
            "sources": sources,
            "summary": summary,
            "available_documents": available_documents,
            "tipos": TipoFuenteVerificacion,
            "tipo_nombres": tipo_nombres,
            "is_counterpart": True,
            "t": t,
        },
    )


@router.post("/contraparte/{project_id}/indicators/{indicator_id}/verification-sources", response_class=HTMLResponse)
def counterpart_add_indicator_source(
    request: Request,
    project_id: int,
    indicator_id: int,
    document_id: int = Form(...),
    tipo: TipoFuenteVerificacion = Form(...),
    descripcion: str | None = Form(None),
    session: CounterpartSession = Depends(get_current_counterpart),
    project_service: ProjectService = Depends(get_project_service),
    verification_service: VerificationSourceService = Depends(get_verification_service),
    db: Session = Depends(get_db),
):
    """Vincular documento a indicador como fuente de verificacion (contraparte)."""
    project = _validate_counterpart_project(session, project_id, project_service)

    indicator = db.get(Indicator, indicator_id)
    if not indicator or indicator.framework.project_id != project_id:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")

    # Validar que el documento pertenece al proyecto
    from app.models.document import Document
    document = db.get(Document, document_id)
    if not document or document.project_id != project_id:
        raise HTTPException(status_code=400, detail="Documento no encontrado o no pertenece al proyecto")

    try:
        data = VerificationSourceCreate(
            document_id=document_id,
            indicator_id=indicator_id,
            tipo=tipo,
            descripcion=descripcion,
        )
        verification_service.create_source(data)

        # Audit log
        audit = AuditService(db)
        audit.log(
            actor_type=ActorType.counterpart,
            actor_id=str(session.id),
            actor_email=None,
            actor_label=f"Contraparte ({project.codigo_contable})",
            accion=AccionAuditoria.create,
            recurso="verification_source",
            recurso_id=None,
            detalle={"indicator_id": indicator_id, "document_id": document_id},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    lang = session.language or "es"
    t = get_translator(lang)
    tipo_nombres = TIPO_FUENTE_NOMBRES_I18N.get(lang, TIPO_FUENTE_NOMBRES)

    sources = verification_service.get_indicator_sources(indicator_id)
    summary = verification_service.get_indicator_summary(indicator_id)
    available_documents = verification_service.get_available_documents(project_id)

    return templates.TemplateResponse(
        "partials/projects/verification_sources_modal.html",
        {
            "request": request,
            "target_type": "indicator",
            "target_id": indicator_id,
            "target": indicator,
            "project_id": project_id,
            "sources": sources,
            "summary": summary,
            "available_documents": available_documents,
            "tipos": TipoFuenteVerificacion,
            "tipo_nombres": tipo_nombres,
            "is_counterpart": True,
            "t": t,
        },
    )


@router.post("/contraparte/{project_id}/activities/{activity_id}/verification-sources", response_class=HTMLResponse)
def counterpart_add_activity_source(
    request: Request,
    project_id: int,
    activity_id: int,
    document_id: int = Form(...),
    tipo: TipoFuenteVerificacion = Form(...),
    descripcion: str | None = Form(None),
    session: CounterpartSession = Depends(get_current_counterpart),
    project_service: ProjectService = Depends(get_project_service),
    verification_service: VerificationSourceService = Depends(get_verification_service),
    db: Session = Depends(get_db),
):
    """Vincular documento a actividad como fuente de verificacion (contraparte)."""
    project = _validate_counterpart_project(session, project_id, project_service)

    activity = db.get(Activity, activity_id)
    if not activity or activity.result.objective.framework.project_id != project_id:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    # Validar que el documento pertenece al proyecto
    from app.models.document import Document
    document = db.get(Document, document_id)
    if not document or document.project_id != project_id:
        raise HTTPException(status_code=400, detail="Documento no encontrado o no pertenece al proyecto")

    try:
        data = VerificationSourceCreate(
            document_id=document_id,
            activity_id=activity_id,
            tipo=tipo,
            descripcion=descripcion,
        )
        verification_service.create_source(data)

        # Audit log
        audit = AuditService(db)
        audit.log(
            actor_type=ActorType.counterpart,
            actor_id=str(session.id),
            actor_email=None,
            actor_label=f"Contraparte ({project.codigo_contable})",
            accion=AccionAuditoria.create,
            recurso="verification_source",
            recurso_id=None,
            detalle={"activity_id": activity_id, "document_id": document_id},
            ip_address=request.client.host if request.client else None,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    lang = session.language or "es"
    t = get_translator(lang)
    tipo_nombres = TIPO_FUENTE_NOMBRES_I18N.get(lang, TIPO_FUENTE_NOMBRES)

    sources = verification_service.get_activity_sources(activity_id)
    summary = verification_service.get_activity_summary(activity_id)
    available_documents = verification_service.get_available_documents(project_id)

    return templates.TemplateResponse(
        "partials/projects/verification_sources_modal.html",
        {
            "request": request,
            "target_type": "activity",
            "target_id": activity_id,
            "target": activity,
            "project_id": project_id,
            "sources": sources,
            "summary": summary,
            "available_documents": available_documents,
            "tipos": TipoFuenteVerificacion,
            "tipo_nombres": tipo_nombres,
            "is_counterpart": True,
            "t": t,
        },
    )
