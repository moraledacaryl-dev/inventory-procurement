import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from app.api.deps import SESSION_COOKIE_NAME
from app.api.router import api_router
from app.core.config import settings

app = FastAPI(title=settings.app_name, version="1.0.0", docs_url="/docs" if settings.app_env != "production" else None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID", "X-Requested-With", "X-Integration-Token"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.max_request_bytes:
        return JSONResponse(status_code=413, content={"detail": "Request body too large", "request_id": request_id}, headers={"x-request-id": request_id})

    is_login = request.url.path == f"{settings.api_v1_prefix}/auth/login"
    service_authenticated = bool(request.headers.get("x-integration-token"))
    cookie_authenticated_mutation = (
        request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and not is_login
        and not service_authenticated
        and request.cookies.get(SESSION_COOKIE_NAME)
        and not request.headers.get("authorization")
    )
    if cookie_authenticated_mutation and request.headers.get("x-requested-with") != "HiddenOasisInventory":
        return JSONResponse(
            status_code=403,
            content={"detail": "Missing session request verification", "request_id": request_id},
            headers={"x-request-id": request_id},
        )

    try:
        response = await call_next(request)
    except Exception:
        response = JSONResponse(status_code=500, content={"detail": "Internal server error", "request_id": request_id})
    response.headers["x-request-id"] = request_id
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["x-frame-options"] = "DENY"
    response.headers["referrer-policy"] = "no-referrer"
    response.headers["permissions-policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["content-security-policy"] = "default-src 'none'; frame-ancestors 'none'"
    response.headers["cache-control"] = "no-store"
    if settings.app_env == "production":
        response.headers["strict-transport-security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(api_router, prefix=settings.api_v1_prefix)
