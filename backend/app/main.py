import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse

import app.database.models  # noqa: F401  full metadata so foreign keys resolve
from app.config import settings
from app.core.exceptions import AppError, app_error_handler
from app.modules.analytics.router import router as analytics_router
from app.modules.assessments.router import router as assessments_router
from app.modules.courses.router import router as courses_router
from app.modules.documents.router import router as documents_router
from app.modules.jobs.router import router as jobs_router
from app.modules.lessons.router import router as lessons_router
from app.modules.rag.router import router as rag_router
from app.modules.research.router import router as research_router
from app.modules.syllabus.router import router as syllabus_router
from app.modules.tutor.router import router as tutor_router
from app.modules.users.router import auth_router, users_router
from app.modules.workspaces.router import invitations_router
from app.modules.workspaces.router import router as workspaces_router

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s level=%(levelname)s logger=%(name)s %(message)s",
)

app = FastAPI(title="SemSaviour API")
app.add_exception_handler(AppError, app_error_handler)
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def csrf_guard(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    # Cookie auth (D25): other sites can make a browser send POSTs with our cookies, but not with a custom header
    # (that needs CORS, which isn't enabled). So every state-changing API call must carry one.
    if request.method in UNSAFE and request.url.path.startswith("/api/") and not request.headers.get("x-requested-with"):
        return JSONResponse(status_code=403, content={"detail": "Missing X-Requested-With header."})
    return await call_next(request)

api = APIRouter(prefix="/api/v1")


@api.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


for router in (auth_router, users_router, workspaces_router, invitations_router, courses_router, documents_router, jobs_router,
               rag_router, syllabus_router, research_router, lessons_router, tutor_router, assessments_router, analytics_router):
    api.include_router(router)
app.include_router(api)
