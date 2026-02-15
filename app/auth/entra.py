from authlib.integrations.starlette_client import OAuth
from app.config import get_settings

oauth = OAuth()

settings = get_settings()

if settings.entra_tenant_id and settings.entra_client_id:
    oauth.register(
        name="entra",
        client_id=settings.entra_client_id,
        client_secret=settings.entra_client_secret,
        server_metadata_url=f"https://login.microsoftonline.com/{settings.entra_tenant_id}/v2.0/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
