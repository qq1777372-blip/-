"""Static pages and SPA entry points: PC console, mobile App, tutorials, docs.

Moved out of main.py unchanged. Every handler keeps its absolute path (the router
declares no prefix) so the URL surface is byte-identical -- see
tests/route_snapshot.txt.

Shared dependencies arrive as keyword arguments instead of imports: main.py owns
them, and importing from it here would be a cycle.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from models import AdminUser


def create_pages_router(
    *,
    get_db,
    get_current_user_optional,
    has_admin_users,
    frontend_dist_dir: Path,
    app_frontend_dist_dir: Path,
    tutorials_dist_dir: Path,
    company_expense_app_dir: Path,
) -> APIRouter:
    # The moved bodies reference these as module constants. Aliasing here keeps the
    # factory signature conventional without editing a line of the moved code.
    FRONTEND_DIST_DIR = frontend_dist_dir
    APP_FRONTEND_DIST_DIR = app_frontend_dist_dir
    TUTORIALS_DIST_DIR = tutorials_dist_dir
    COMPANY_EXPENSE_APP_DIR = company_expense_app_dir

    router = APIRouter(tags=["pages"])

    def frontend_index_response() -> FileResponse:
        return FileResponse(
            FRONTEND_DIST_DIR / "index.html",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    def frontend_ui_response(path: str = "") -> FileResponse:
        if not FRONTEND_DIST_DIR.exists():
            raise HTTPException(status_code=404, detail="Frontend build not found")

        requested_path = path.strip("/")
        if not requested_path:
            return frontend_index_response()

        candidate = (FRONTEND_DIST_DIR / requested_path).resolve()
        try:
            candidate.relative_to(FRONTEND_DIST_DIR.resolve())
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc

        if candidate.is_file():
            return FileResponse(candidate)

        return frontend_index_response()

    def app_frontend_index_response() -> FileResponse:
        return FileResponse(
            APP_FRONTEND_DIST_DIR / "index.html",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    def app_frontend_response(path: str = "") -> FileResponse:
        if not APP_FRONTEND_DIST_DIR.exists():
            raise HTTPException(status_code=404, detail="App frontend build not found")

        requested_path = path.strip("/")
        if not requested_path:
            return app_frontend_index_response()

        candidate = (APP_FRONTEND_DIST_DIR / requested_path).resolve()
        try:
            candidate.relative_to(APP_FRONTEND_DIST_DIR.resolve())
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc

        if candidate.is_file():
            return FileResponse(candidate)

        return app_frontend_index_response()

    def is_bare_mobile_webview(request: Request) -> bool:
        user_agent = request.headers.get("user-agent", "").lower()
        if any(marker in user_agent for marker in ("dingtalk", "micromessenger", "alipayclient")):
            return False
        ios_webview = (
            ("iphone" in user_agent or "ipad" in user_agent)
            and "applewebkit" in user_agent
            and "mobile/" in user_agent
            and "safari/" not in user_agent
        )
        android_webview = "android" in user_agent and ("; wv)" in user_agent or " wv" in user_agent)
        return ios_webview or android_webview

    def mobile_app_upgrade_redirect(path: str) -> RedirectResponse:
        target = "/app/login" if path.strip("/").startswith("login") else "/app/tabs/home"
        return RedirectResponse(
            url=f"{target}?app_version=0.7.14-alpha",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    def build_login_redirect_url(target_path: str) -> str:
        normalized_target = target_path if target_path.startswith("/") else f"/{target_path}"
        return f"/ui/login?redirect={quote(normalized_target, safe='/%?=&')}"

    def tutorials_index_response() -> FileResponse:
        return FileResponse(
            TUTORIALS_DIST_DIR / "index.html",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    def tutorials_site_response(path: str = "") -> FileResponse:
        if not TUTORIALS_DIST_DIR.exists():
            raise HTTPException(status_code=404, detail="Tutorial site build not found")

        requested_path = path.strip("/")
        if not requested_path:
            return tutorials_index_response()

        direct_candidate = (TUTORIALS_DIST_DIR / requested_path).resolve()
        tutorials_root = TUTORIALS_DIST_DIR.resolve()
        try:
            direct_candidate.relative_to(tutorials_root)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc

        if direct_candidate.is_file():
            return FileResponse(direct_candidate)

        clean_url_candidate = (TUTORIALS_DIST_DIR / requested_path / "index.html").resolve()
        try:
            clean_url_candidate.relative_to(tutorials_root)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc

        if clean_url_candidate.is_file():
            return FileResponse(clean_url_candidate)

        html_candidate = (TUTORIALS_DIST_DIR / f"{requested_path}.html").resolve()
        try:
            html_candidate.relative_to(tutorials_root)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc

        if html_candidate.is_file():
            return FileResponse(html_candidate)

        raise HTTPException(status_code=404, detail="Tutorial page not found")

    @router.get("/shop-records-admin")
    def shop_record_page(current_user: AdminUser | None = Depends(get_current_user_optional)):
        if current_user is None:
            return RedirectResponse(url="/ui/login", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/ui/shop-records", status_code=status.HTTP_303_SEE_OTHER)

    @router.get("/licenses")
    def license_page(current_user: AdminUser | None = Depends(get_current_user_optional)):
        if current_user is None:
            return RedirectResponse(url="/ui/login", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/ui/licenses", status_code=status.HTTP_303_SEE_OTHER)

    @router.get("/ui")
    def vue_ui_root(request: Request):
        if is_bare_mobile_webview(request):
            return mobile_app_upgrade_redirect("dashboard")
        return frontend_ui_response()

    @router.get("/ui/app")
    def legacy_mobile_app_root():
        return RedirectResponse(url="/app/", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    @router.get("/ui/app/{path:path}")
    def legacy_mobile_app_page(path: str):
        return RedirectResponse(url=f"/app/{path.lstrip('/')}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    @router.get("/ui/{path:path}")
    def vue_ui_page(path: str, request: Request):
        embedded_app = request.query_params.get("embedded_app") == "1"
        if is_bare_mobile_webview(request) and not Path(path).suffix and not embedded_app:
            return mobile_app_upgrade_redirect(path)
        return frontend_ui_response(path)

    @router.get("/app")
    def mobile_app_root():
        return app_frontend_response()

    @router.get("/app/{path:path}")
    def mobile_app_page(path: str):
        return app_frontend_response(path)

    @router.get("/company-expenses-app")
    def company_expenses_app_redirect(
        current_user: AdminUser | None = Depends(get_current_user_optional),
    ):
        if current_user is None:
            return RedirectResponse(
                url=build_login_redirect_url("/company-expenses-app/"),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        return RedirectResponse(url="/company-expenses-app/", status_code=status.HTTP_303_SEE_OTHER)

    @router.get("/company-expenses-app/")
    def company_expenses_app(
        current_user: AdminUser | None = Depends(get_current_user_optional),
    ):
        if current_user is None:
            return RedirectResponse(
                url=build_login_redirect_url("/company-expenses-app/"),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        page_file = COMPANY_EXPENSE_APP_DIR / "index.html"
        if not page_file.is_file():
            raise HTTPException(status_code=404, detail="Company expense app not found")
        return FileResponse(
            page_file,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    @router.get("/tutorials")
    def tutorials_root(current_user: AdminUser | None = Depends(get_current_user_optional)):
        if current_user is None:
            return RedirectResponse(url=build_login_redirect_url("/tutorials/"), status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/tutorials/", status_code=status.HTTP_303_SEE_OTHER)

    @router.get("/tutorials/")
    def tutorials_index(
        request: Request,
        current_user: AdminUser | None = Depends(get_current_user_optional),
    ):
        if current_user is None:
            return RedirectResponse(
                url=build_login_redirect_url(request.url.path),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        return tutorials_site_response()

    @router.get("/tutorials/{path:path}")
    def tutorials_page(
        path: str,
        request: Request,
        current_user: AdminUser | None = Depends(get_current_user_optional),
    ):
        if current_user is None:
            return RedirectResponse(
                url=build_login_redirect_url(request.url.path),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        return tutorials_site_response(path)

    @router.get("/login")
    def login_page(
        current_user: AdminUser | None = Depends(get_current_user_optional),
        db: Session = Depends(get_db),
    ):
        if current_user is not None:
            return RedirectResponse(url="/ui/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        if not has_admin_users(db) and settings.public_registration_enabled:
            return RedirectResponse(url="/ui/login", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/ui/login", status_code=status.HTTP_303_SEE_OTHER)

    @router.get("/register")
    def register_page(
        current_user: AdminUser | None = Depends(get_current_user_optional),
        db: Session = Depends(get_db),
    ):
        if current_user is not None:
            return RedirectResponse(url="/ui/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        if has_admin_users(db) and not settings.public_registration_enabled:
            return RedirectResponse(url="/ui/login", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/ui/login", status_code=status.HTTP_303_SEE_OTHER)

    return router
