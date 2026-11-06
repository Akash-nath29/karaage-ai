import uuid

from fastapi import APIRouter, Request, Response, UploadFile
from fastapi.responses import RedirectResponse

from app.config import settings
from app.core import security
from app.core.permissions import CurrentUser
from app.database.session import DbSession
from app.modules.users import service
from app.modules.users.schemas import EmailIn, LoginIn, PasswordIn, ProfilePatch, RegisterIn, ResetIn, TokenIn, UserOut

auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])
REFRESH_PATH = "/api/v1/auth"  # the refresh cookie only travels to the auth endpoints


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _set_session(response: Response, user_id: uuid.UUID, refresh: str) -> None:
    common = {"httponly": True, "samesite": "lax", "secure": settings.cookie_secure}
    response.set_cookie("access_token", security.access_token(user_id), max_age=settings.access_token_minutes * 60,
                        path="/", **common)  # type: ignore[arg-type]
    response.set_cookie("refresh_token", refresh, max_age=settings.refresh_token_days * 86400, path=REFRESH_PATH,
                        **common)  # type: ignore[arg-type]


@auth_router.post("/register", response_model=UserOut, status_code=201)
def register(data: RegisterIn, request: Request, response: Response, db: DbSession) -> UserOut:
    """Creates the account, signs in, and emails a confirmation link (sign-in doesn't wait for it, A19)."""
    user, refresh = service.register(db, data, _ip(request))
    _set_session(response, user.id, refresh)
    return service.out(user)


@auth_router.post("/login", response_model=UserOut)
def login(data: LoginIn, request: Request, response: Response, db: DbSession) -> UserOut:
    user, refresh = service.login(db, data, _ip(request))
    _set_session(response, user.id, refresh)
    return service.out(user)


@auth_router.post("/refresh", status_code=204)
def refresh(request: Request, response: Response, db: DbSession) -> None:
    """New access token + rotated refresh token (cookies)."""
    user_id, token = service.refresh(db, request.cookies.get("refresh_token"), _ip(request))
    _set_session(response, user_id, token)


@auth_router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: DbSession) -> None:
    service.logout(db, request.cookies.get("refresh_token"))
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path=REFRESH_PATH)


@auth_router.post("/verify-email", status_code=204)
def verify_email(data: TokenIn, db: DbSession) -> None:
    service.verify_email(db, data.token)


@auth_router.post("/resend-verification", status_code=202)
def resend_verification(user: CurrentUser, db: DbSession) -> None:
    service.resend_verification(db, user)


@auth_router.post("/forgot-password", status_code=202)
def forgot_password(data: EmailIn, request: Request, db: DbSession) -> None:
    service.forgot_password(db, data.email, _ip(request))


@auth_router.post("/reset-password", status_code=204)
def reset_password(data: ResetIn, request: Request, db: DbSession) -> None:
    service.reset_password(db, data, _ip(request))


@users_router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return service.out(user)


@users_router.patch("/me", response_model=UserOut)
def update_me(data: ProfilePatch, user: CurrentUser, db: DbSession) -> UserOut:
    return service.out(service.update_profile(db, user, data))


@users_router.delete("/me", status_code=204)
def delete_me(data: PasswordIn, response: Response, user: CurrentUser, db: DbSession) -> None:
    """Delete your account, your private data, and the workspaces you own (§10.5). Needs your password."""
    service.delete_account(db, user, data.password)
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path=REFRESH_PATH)


@users_router.put("/me/avatar", response_model=UserOut)
def set_avatar(file: UploadFile, user: CurrentUser, db: DbSession) -> UserOut:
    return service.out(service.set_avatar(db, user, file.file.read(service.AVATAR_MAX_BYTES + 1)))


@users_router.delete("/me/avatar", response_model=UserOut)
def remove_avatar(user: CurrentUser, db: DbSession) -> UserOut:
    return service.out(service.remove_avatar(db, user))


@users_router.get("/{user_id}/avatar", status_code=307)
def avatar(user_id: uuid.UUID, _: CurrentUser, db: DbSession) -> RedirectResponse:
    return RedirectResponse(service.avatar_file_url(db, user_id), status_code=307)
