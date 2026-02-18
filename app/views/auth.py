from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import get_settings
from app.auth.entra import oauth
from app.auth.session import (
    create_internal_session, destroy_internal_session,
    create_counterpart_session, validate_project_code,
    set_counterpart_cookie, clear_counterpart_cookie,
)
from app.models.user import User
from app.services.user_service import UserService
from app.services.audit_service import AuditService
from app.models.audit_log import ActorType, AccionAuditoria
from app.i18n import detect_language, get_translator

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    has_entra = bool(settings.entra_client_id and settings.entra_tenant_id)
    return templates.TemplateResponse(
        "pages/auth/login.html",
        {"request": request, "has_entra": has_entra, "debug": settings.debug},
    )


@router.get("/auth/callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.entra.authorize_access_token(request)
    except Exception as e:
        import logging
        logging.getLogger("cooperapp.auth").error(f"OAuth callback failed: {type(e).__name__}: {e}")
        return RedirectResponse(url="/login?error=auth_failed", status_code=302)

    userinfo = token.get("userinfo", {})
    oid = userinfo.get("oid") or userinfo.get("sub", "")
    email = userinfo.get("email") or userinfo.get("preferred_username", "")
    nombre = userinfo.get("given_name", "")
    apellidos = userinfo.get("family_name", "")

    if not email:
        return RedirectResponse(url="/login?error=no_email", status_code=302)

    service = UserService(db)
    user = service.get_or_create_from_entra(oid, email, nombre, apellidos)

    create_internal_session(request, user)

    # Auditar login
    audit = AuditService(db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=user.id,
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.login,
        ip_address=request.client.host if request.client else None,
    )

    if not user.rol:
        return RedirectResponse(url="/pendiente", status_code=302)

    return RedirectResponse(url="/projects", status_code=302)


@router.get("/auth/login-entra")
async def login_entra(request: Request):
    redirect_uri = f"{settings.app_url}/auth/callback"
    return await oauth.entra.authorize_redirect(request, redirect_uri)


@router.post("/auth/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            audit = AuditService(db)
            audit.log(
                actor_type=ActorType.internal,
                actor_id=user.id,
                actor_email=user.email,
                actor_label=user.nombre_completo,
                accion=AccionAuditoria.logout,
                ip_address=request.client.host if request.client else None,
            )
    destroy_internal_session(request)
    return RedirectResponse(url="/login", status_code=302)


@router.get("/contraparte/login", response_class=HTMLResponse)
def counterpart_login_page(request: Request):
    error = request.query_params.get("error")
    lang = request.query_params.get("lang")
    if not lang:
        lang = detect_language(request.headers.get("accept-language"))
    t = get_translator(lang)
    return templates.TemplateResponse(
        "pages/auth/counterpart_login.html",
        {"request": request, "error": error, "lang": lang, "t": t},
    )


@router.post("/contraparte/login")
async def counterpart_login(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    code = form_data.get("code", "").strip()
    language = form_data.get("language", "es")

    if not code:
        return RedirectResponse(url=f"/contraparte/login?error=empty&lang={language}", status_code=302)

    ip = request.client.host if request.client else None
    project = validate_project_code(db, code)

    if not project:
        # Auditar login fallido
        audit = AuditService(db)
        audit.log(
            actor_type=ActorType.counterpart,
            actor_id="unknown",
            actor_email=None,
            actor_label="Contraparte (codigo invalido)",
            accion=AccionAuditoria.login_failed,
            detalle={"code_provided": code[:4] + "***"},
            ip_address=ip,
        )
        return RedirectResponse(url=f"/contraparte/login?error=invalid&lang={language}", status_code=302)

    user_agent = request.headers.get("user-agent", "")
    session = create_counterpart_session(db, project.id, ip, user_agent, language=language)

    # Auditar login contraparte
    audit = AuditService(db)
    audit.log(
        actor_type=ActorType.counterpart,
        actor_id=session.id,
        actor_email=None,
        actor_label=f"Contraparte - {project.titulo}",
        accion=AccionAuditoria.login,
        recurso="project",
        recurso_id=str(project.id),
        ip_address=ip,
        project_id=project.id,
    )

    response = RedirectResponse(url=f"/contraparte/{project.id}", status_code=302)
    set_counterpart_cookie(response, session.session_token)
    return response


@router.post("/contraparte/logout")
def counterpart_logout(request: Request, db: Session = Depends(get_db)):
    from app.models.counterpart_session import CounterpartSession
    token = request.cookies.get("counterpart_token")
    lang = "es"
    if token:
        session = db.query(CounterpartSession).filter(
            CounterpartSession.session_token == token
        ).first()
        if session:
            lang = session.language or "es"
            audit = AuditService(db)
            audit.log(
                actor_type=ActorType.counterpart,
                actor_id=session.id,
                actor_email=None,
                actor_label=f"Contraparte - Proyecto #{session.project_id}",
                accion=AccionAuditoria.logout,
                project_id=session.project_id,
                ip_address=request.client.host if request.client else None,
            )
            session.activo = False
            db.commit()

    response = RedirectResponse(url=f"/contraparte/login?lang={lang}", status_code=302)
    clear_counterpart_cookie(response)
    return response


@router.get("/pendiente", response_class=HTMLResponse)
def pending_page(request: Request):
    return templates.TemplateResponse(
        "pages/auth/pending.html",
        {"request": request},
    )


@router.get("/unauthorized", response_class=HTMLResponse)
def unauthorized_page(request: Request):
    return templates.TemplateResponse(
        "pages/auth/unauthorized.html",
        {"request": request},
    )


@router.get("/dev-login")
def dev_login(request: Request, db: Session = Depends(get_db)):
    if not settings.debug:
        return RedirectResponse(url="/login", status_code=302)

    service = UserService(db)
    user = service.get_or_create_dev_user()
    create_internal_session(request, user)

    audit = AuditService(db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=user.id,
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.login,
        detalle={"method": "dev-login"},
        ip_address=request.client.host if request.client else None,
    )

    return RedirectResponse(url="/projects", status_code=302)


@router.get("/dev-login/{rol}")
def dev_login_role(request: Request, rol: str, db: Session = Depends(get_db)):
    if not settings.debug:
        return RedirectResponse(url="/login", status_code=302)

    from app.models.user import Rol
    try:
        rol_enum = Rol(rol)
    except ValueError:
        return RedirectResponse(url="/login", status_code=302)

    service = UserService(db)
    user = service.get_or_create_dev_user_with_role(rol_enum)
    create_internal_session(request, user)

    audit = AuditService(db)
    audit.log(
        actor_type=ActorType.internal,
        actor_id=user.id,
        actor_email=user.email,
        actor_label=user.nombre_completo,
        accion=AccionAuditoria.login,
        detalle={"method": "dev-login", "rol": rol},
        ip_address=request.client.host if request.client else None,
    )

    return RedirectResponse(url="/projects", status_code=302)
