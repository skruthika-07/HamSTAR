from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .api import attempts, auth, diagnostics, evaluation, mistakes, notes, answer_images, practice, tasks, profile, progress, questions, study_materials
from .core import errors
from .core.config import get_settings
from .core.database import Base, SessionLocal, engine
from .core.logging import log
from .services import bank_service, pdf_service, reminder_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    # `alembic upgrade head` is the real migration path; this keeps a first local run working without it
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        bank_service.seed(db)
    s = get_settings()
    log.info("HamSTAR API ready. Mistral %s, Groq %s.", "configured" if s.mistral_api_key else "not configured", "configured" if s.groq_api_key else "not configured")
    if not pdf_service.library():
        log.warning("No PDF library is installed in this environment; it will be installed on the first PDF download.")
    scheduler = reminder_service.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="HamSTAR API",
    version="1.0.0",
    description=(
        "Detect the misconception, not the wrong answer.\n\n"
        "A wrong answer opens an investigation: the specific wrong option → evidence → competing hypotheses → "
        "a discriminating follow-up → re-evaluation → a confidence. A diagnosis is stated only above 70%.\n\n"
        "All routes under `/api` except register, login and the password reset need `Authorization: Bearer <token>`. "
        "Responses are `{success, data}` or `{success: false, error: {code, message}}`."
    ),
    lifespan=lifespan,
)

@app.middleware("http")
async def unexpected_errors(request: Request, call_next):
    """Sits inside CORS, so even an unexpected failure reaches the browser as a readable error."""
    try:
        return await call_next(request)
    except Exception:  # noqa: BLE001
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Something went wrong on our side. Please try again."}}, status_code=500)


app.add_middleware(CORSMiddleware, allow_origins=get_settings().origins, allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"], expose_headers=["Content-Disposition"])
errors.install(app)

for module in (auth, study_materials, questions, attempts, diagnostics, mistakes, progress, profile, evaluation, practice, notes, tasks, answer_images):
    app.include_router(module.router)


@app.get("/health", tags=["Health"], summary="Liveness and database check")
def health():
    """Cheap by design: it never calls an AI provider."""
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:  # noqa: BLE001
        log.exception("Health check: database unreachable")
        return {"status": "degraded", "database": "disconnected"}
