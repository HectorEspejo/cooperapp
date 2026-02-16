from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
from fastapi import Request
from app.database import SessionLocal
from app.models.user import User
from app.models.counterpart_session import CounterpartSession


class AuthMiddleware(BaseHTTPMiddleware):
    RUTAS_PUBLICAS = {"/login", "/auth/login-entra", "/auth/callback", "/contraparte/login", "/health", "/dev-login", "/pendiente", "/unauthorized"}
    PREFIJOS_PUBLICOS = ["/static", "/docs", "/openapi.json", "/redoc"]

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip public routes
        if path in self.RUTAS_PUBLICAS:
            return await call_next(request)

        for prefix in self.PREFIJOS_PUBLICOS:
            if path.startswith(prefix):
                return await call_next(request)

        # Counterpart routes
        if path.startswith("/contraparte/"):
            if path == "/contraparte/logout":
                return await call_next(request)

            token = request.cookies.get("counterpart_token")
            if not token:
                return RedirectResponse(url="/contraparte/login", status_code=302)

            db = SessionLocal()
            try:
                session = db.query(CounterpartSession).filter(
                    CounterpartSession.session_token == token
                ).first()
                if not session or not session.is_valid:
                    return RedirectResponse(url="/contraparte/login", status_code=302)
                request.state.counterpart_session = session
            finally:
                db.close()

            return await call_next(request)

        # Internal routes - check session
        user_id = request.session.get("user_id") if hasattr(request, "session") else None
        if not user_id:
            # API routes return 401
            if path.startswith("/api/"):
                from starlette.responses import JSONResponse
                return JSONResponse({"detail": "No autenticado"}, status_code=401)
            return RedirectResponse(url="/login", status_code=302)

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.activo:
                request.session.clear()
                if path.startswith("/api/"):
                    from starlette.responses import JSONResponse
                    return JSONResponse({"detail": "No autenticado"}, status_code=401)
                return RedirectResponse(url="/login", status_code=302)

            if not user.rol and path not in ("/pendiente",):
                return RedirectResponse(url="/pendiente", status_code=302)

            request.state.user = user
        finally:
            db.close()

        return await call_next(request)
