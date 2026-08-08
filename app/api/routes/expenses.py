"""Company and personal expense records, the shared expense category
configuration, and the Apple Shortcuts entry point that files an expense from a
phone.

These four prefixes are one batch on purpose. /expense-shortcut and
/expense-categories look like small standalone domains, but both drive the same
machinery -- serialize_company_expense, serialize_personal_expense and the
category resolver -- so splitting them apart would mean threading that machinery
across a module boundary for no gain."""

from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import secrets
from datetime import date as date_type
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import AdminUser, AppSetting, CompanyExpenseRecord, PersonalExpenseRecord
from schemas import (
    CompanyExpenseCreate,
    CompanyExpenseResponse,
    CompanyExpenseStatusUpdate,
    CompanyExpenseSummaryResponse,
    CompanyExpenseUpdate,
    ExpenseCategoryListResponse,
    ExpenseCategoryUpdateRequest,
    ExpenseShortcutRecordRequest,
    PersonalExpenseCreate,
    PersonalExpenseResponse,
    PersonalExpenseSummaryResponse,
    PersonalExpenseUpdate,
)


def create_expenses_router(
    *,
    get_db,
    require_role,
    commit_session,
    write_audit_log,
    create_sqlite_backup,
    get_setting,
    read_json_setting,
    write_json_setting,
    build_admin_user_public_name,
    company_expense_upload_dir,
    personal_expense_upload_dir,
    expense_shortcut_setting_prefix,
    expense_shortcut_auth_scheme,
    expense_categories_key,
    default_expense_categories,
    role_levels,
) -> APIRouter:
    # The moved bodies still spell these as main.py globals. Aliasing here
    # keeps the factory signature conventional while leaving every copied
    # line untouched.
    COMPANY_EXPENSE_UPLOAD_DIR = company_expense_upload_dir
    PERSONAL_EXPENSE_UPLOAD_DIR = personal_expense_upload_dir
    EXPENSE_SHORTCUT_SETTING_PREFIX = expense_shortcut_setting_prefix
    EXPENSE_SHORTCUT_AUTH_SCHEME = expense_shortcut_auth_scheme
    EXPENSE_CATEGORIES_KEY = expense_categories_key
    DEFAULT_EXPENSE_CATEGORIES = default_expense_categories
    ROLE_LEVELS = role_levels

    router = APIRouter(tags=["expenses"])

    def build_company_expense_no(record: CompanyExpenseRecord) -> str:
        return f"CE-{record.expense_date.strftime('%Y%m%d')}-{record.id:06d}"

    def build_company_expense_attachment_url(record: CompanyExpenseRecord) -> str | None:
        if not record.attachment_path:
            return None
        return f"/company-expenses/{record.id}/attachment-file?v={Path(record.attachment_path).name}"

    def serialize_company_expense(record: CompanyExpenseRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "expense_no": build_company_expense_no(record),
            "expense_date": record.expense_date,
            "amount": float(record.amount or 0),
            "category": record.category,
            "payment_type": record.payment_type,
            "payment_account": record.payment_account,
            "expense_scope": record.expense_scope,
            "description": record.description,
            "approval_status": record.approval_status,
            "reimbursement_status": record.reimbursement_status,
            "submitter_user_id": record.submitter_user_id,
            "submitter_name": record.submitter_name,
            "reviewer_name": record.reviewer_name,
            "reviewed_at": record.reviewed_at,
            "attachment_url": build_company_expense_attachment_url(record),
            "attachment_name": record.attachment_name,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    def build_personal_expense_no(record: PersonalExpenseRecord) -> str:
        return f"PE-{record.record_date.strftime('%Y%m%d')}-{record.id:06d}"

    def build_personal_expense_attachment_url(record: PersonalExpenseRecord) -> str | None:
        if not record.attachment_path:
            return None
        return f"/personal-expenses/{record.id}/attachment-file?v={Path(record.attachment_path).name}"

    def serialize_personal_expense(record: PersonalExpenseRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "record_no": build_personal_expense_no(record),
            "record_date": record.record_date,
            "amount": float(record.amount or 0),
            "transaction_type": record.transaction_type,
            "category": record.category,
            "payment_account": record.payment_account,
            "description": record.description,
            "owner_user_id": record.owner_user_id,
            "owner_name": record.owner_name,
            "attachment_url": build_personal_expense_attachment_url(record),
            "attachment_name": record.attachment_name,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    def get_expense_shortcut_setting(db: Session, user_id: int) -> AppSetting | None:
        return get_setting(db, f"{EXPENSE_SHORTCUT_SETTING_PREFIX}{user_id}")

    def hash_expense_shortcut_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def read_expense_shortcut_setting(db: Session, user_id: int) -> dict[str, Any]:
        setting = get_expense_shortcut_setting(db, user_id)
        if setting is None:
            return {}
        try:
            value = json.loads(setting.value)
        except (TypeError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}

    def write_expense_shortcut_setting(db: Session, user_id: int, value: dict[str, Any]) -> None:
        storage_key = f"{EXPENSE_SHORTCUT_SETTING_PREFIX}{user_id}"
        serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        setting = get_setting(db, storage_key)
        if setting is None:
            db.add(AppSetting(key=storage_key, value=serialized))
        else:
            setting.value = serialized

    def get_company_expense_or_404(db: Session, record_id: int) -> CompanyExpenseRecord:
        record = db.get(CompanyExpenseRecord, record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="公司消费记录不存在")
        return record

    async def save_company_expense_attachment(record: CompanyExpenseRecord, upload: UploadFile) -> None:
        original_name = Path(upload.filename or "expense-proof").name
        suffix = Path(original_name).suffix.lower()
        allowed_suffixes = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}
        if suffix not in allowed_suffixes:
            raise HTTPException(status_code=400, detail="仅支持 JPG、PNG、WEBP、GIF 或 PDF 凭证")

        content = await upload.read()
        if not content:
            raise HTTPException(status_code=400, detail="凭证文件不能为空")
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="凭证文件不能超过 20MB")

        filename = f"expense_{record.id}_{secrets.token_hex(8)}{suffix}"
        save_path = COMPANY_EXPENSE_UPLOAD_DIR / filename
        save_path.write_bytes(content)
        record.attachment_path = str(save_path)
        record.attachment_name = original_name

    def get_personal_expense_or_404(
        db: Session,
        record_id: int,
        current_user: AdminUser,
    ) -> PersonalExpenseRecord:
        record = db.get(PersonalExpenseRecord, record_id)
        if record is None or record.owner_user_id != current_user.id:
            raise HTTPException(status_code=404, detail="?????????")
        return record

    async def save_personal_expense_attachment(record: PersonalExpenseRecord, upload: UploadFile) -> None:
        original_name = Path(upload.filename or "personal-expense-proof").name
        suffix = Path(original_name).suffix.lower()
        allowed_suffixes = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}
        if suffix not in allowed_suffixes:
            raise HTTPException(status_code=400, detail="??? JPG?PNG?WEBP?GIF ? PDF ??")
        content = await upload.read()
        if not content:
            raise HTTPException(status_code=400, detail="????????")
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="???????? 20MB")
        filename = f"personal_expense_{record.id}_{secrets.token_hex(8)}{suffix}"
        save_path = PERSONAL_EXPENSE_UPLOAD_DIR / filename
        save_path.write_bytes(content)
        record.attachment_path = str(save_path)
        record.attachment_name = original_name

    def get_expense_shortcut_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(EXPENSE_SHORTCUT_AUTH_SCHEME),
        db: Session = Depends(get_db),
    ) -> AdminUser:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="\u7f3a\u5c11\u5feb\u6377\u8bb0\u8d26\u4ee4\u724c")
        token = credentials.credentials.strip()
        if not token:
            raise HTTPException(status_code=401, detail="\u5feb\u6377\u8bb0\u8d26\u4ee4\u724c\u65e0\u6548")
        token_hash = hash_expense_shortcut_token(token)
        settings_rows = db.scalars(
            select(AppSetting).where(AppSetting.key.like(f"{EXPENSE_SHORTCUT_SETTING_PREFIX}%"))
        ).all()
        for setting in settings_rows:
            try:
                stored = json.loads(setting.value)
            except (TypeError, ValueError):
                continue
            stored_hash = str(stored.get("token_hash") or "") if isinstance(stored, dict) else ""
            if not stored_hash or not hmac.compare_digest(stored_hash, token_hash):
                continue
            try:
                user_id = int(setting.key.removeprefix(EXPENSE_SHORTCUT_SETTING_PREFIX))
            except ValueError:
                break
            user = db.get(AdminUser, user_id)
            if user is None or not user.is_active:
                break
            return user
        raise HTTPException(status_code=401, detail="\u5feb\u6377\u8bb0\u8d26\u4ee4\u724c\u65e0\u6548\u6216\u5df2\u64a4\u9500")

    def resolve_expense_categories(db: Session) -> tuple[list[str], bool]:
        stored = read_json_setting(db, EXPENSE_CATEGORIES_KEY, None)
        if not isinstance(stored, list):
            return list(DEFAULT_EXPENSE_CATEGORIES), True
        cleaned: list[str] = []
        for item in stored:
            name = str(item or "").strip()
            if name and name not in cleaned:
                cleaned.append(name)
        if not cleaned:
            return list(DEFAULT_EXPENSE_CATEGORIES), True
        return cleaned, False

    def build_expense_category_usage(db: Session) -> dict[str, int]:
        usage: dict[str, int] = {}
        for model in (CompanyExpenseRecord, PersonalExpenseRecord):
            rows = db.execute(
                select(model.category, func.count(model.id)).group_by(model.category),
            ).all()
            for name, count in rows:
                key = str(name or "").strip()
                if not key:
                    continue
                usage[key] = usage.get(key, 0) + int(count or 0)
        return usage

    def build_expense_category_payload(db: Session) -> dict[str, Any]:
        categories, is_default = resolve_expense_categories(db)
        usage = build_expense_category_usage(db)
        return {
            "categories": categories,
            "is_default": is_default,
            "usage": usage,
            "orphan_categories": sorted(name for name in usage if name not in categories),
        }

    @router.get(
        "/expense-categories",
        response_model=ExpenseCategoryListResponse,
        summary="List configurable expense categories",
    )
    def list_expense_categories(
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        return build_expense_category_payload(db)

    @router.put(
        "/expense-categories",
        response_model=ExpenseCategoryListResponse,
        summary="Replace expense categories (handles rename, reorder, add and remove)",
    )
    def replace_expense_categories(
        payload: ExpenseCategoryUpdateRequest,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        write_json_setting(db, EXPENSE_CATEGORIES_KEY, payload.categories)
        commit_session(db, default_detail="Failed to save expense categories")
        return build_expense_category_payload(db)

    @router.delete(
        "/expense-categories",
        response_model=ExpenseCategoryListResponse,
        summary="Reset expense categories back to the built-in defaults",
    )
    def reset_expense_categories(
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        write_json_setting(db, EXPENSE_CATEGORIES_KEY, list(DEFAULT_EXPENSE_CATEGORIES))
        commit_session(db, default_detail="Failed to reset expense categories")
        return build_expense_category_payload(db)

    @router.get("/expense-shortcut/token", summary="Get Apple Shortcut bookkeeping token status")
    def get_expense_shortcut_token_status(
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("viewer")),
    ):
        stored = read_expense_shortcut_setting(db, current_user.id)
        return {
            "enabled": bool(stored.get("token_hash")),
            "created_at": stored.get("created_at"),
            "endpoint": "/expense-shortcut/record",
        }

    @router.post("/expense-shortcut/token", summary="Create or rotate Apple Shortcut bookkeeping token")
    def create_expense_shortcut_token(
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("viewer")),
    ):
        raw_token = f"xse_{secrets.token_urlsafe(32)}"
        created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        write_expense_shortcut_setting(
            db,
            current_user.id,
            {"token_hash": hash_expense_shortcut_token(raw_token), "created_at": created_at},
        )
        write_audit_log(
            db,
            actor=current_user,
            action="expense_shortcut_token_rotated",
            resource_type="expense_shortcut_token",
            resource_id=current_user.id,
            details={"created_at": created_at},
        )
        commit_session(db, default_detail="Failed to create expense shortcut token")
        return {
            "enabled": True,
            "created_at": created_at,
            "endpoint": "/expense-shortcut/record",
            "token": raw_token,
        }

    @router.delete("/expense-shortcut/token", summary="Revoke Apple Shortcut bookkeeping token")
    def revoke_expense_shortcut_token(
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("viewer")),
    ):
        setting = get_expense_shortcut_setting(db, current_user.id)
        if setting is not None:
            db.delete(setting)
        write_audit_log(
            db,
            actor=current_user,
            action="expense_shortcut_token_revoked",
            resource_type="expense_shortcut_token",
            resource_id=current_user.id,
            details={},
        )
        commit_session(db, default_detail="Failed to revoke expense shortcut token")
        return {"enabled": False}

    @router.post("/expense-shortcut/record", status_code=status.HTTP_201_CREATED, summary="Create expense from Apple Shortcuts")
    def create_expense_from_shortcut(
        payload: ExpenseShortcutRecordRequest,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(get_expense_shortcut_user),
    ):
        book = payload.book.strip().lower()
        record_date = payload.date or date_type.today()
        category = payload.category.strip()
        note = payload.note.strip()
        payment_account = payload.payment_account.strip() or "\u5feb\u6377\u6307\u4ee4"

        if book == "personal":
            transaction_type = payload.transaction_type.strip().lower()
            if transaction_type not in {"expense", "income"}:
                raise HTTPException(status_code=400, detail="\u4e2a\u4eba\u8d26\u672c\u7c7b\u578b\u53ea\u80fd\u662f expense \u6216 income")
            category = category or ("\u5176\u4ed6\u6536\u5165" if transaction_type == "income" else "\u65e5\u5e38\u6d88\u8d39")
            record = PersonalExpenseRecord(
                record_date=record_date,
                amount=payload.amount,
                transaction_type=transaction_type,
                category=category,
                payment_account=payment_account,
                description=note or category,
                owner_user_id=current_user.id,
                owner_name=build_admin_user_public_name(current_user),
            )
            db.add(record)
            commit_session(db, default_detail="Failed to create personal expense from shortcut")
            db.refresh(record)
            serialized_record = serialize_personal_expense(record)
            action = "personal_expense_created_from_shortcut"
            resource_type = "personal_expense"
            message = "\u4e2a\u4eba\u8bb0\u8d26\u6210\u529f"
        elif book == "company":
            if ROLE_LEVELS.get(current_user.role, 0) < ROLE_LEVELS["editor"]:
                raise HTTPException(status_code=403, detail="\u5f53\u524d\u8d26\u53f7\u6ca1\u6709\u516c\u53f8\u8bb0\u8d26\u6743\u9650")
            payment_type = payload.payment_type.strip().lower()
            if payment_type not in {"company", "employee"}:
                raise HTTPException(status_code=400, detail="\u516c\u53f8\u652f\u4ed8\u7c7b\u578b\u53ea\u80fd\u662f company \u6216 employee")
            category = category or "\u5176\u4ed6\u6d88\u8d39"
            record = CompanyExpenseRecord(
                expense_date=record_date,
                amount=payload.amount,
                category=category,
                payment_type=payment_type,
                payment_account=payment_account,
                expense_scope=payload.expense_scope.strip() or "\u516c\u5171\u8d39\u7528",
                description=note or category,
                approval_status="approved",
                reimbursement_status="not_required",
                submitter_user_id=current_user.id,
                submitter_name=build_admin_user_public_name(current_user),
            )
            db.add(record)
            commit_session(db, default_detail="Failed to create company expense from shortcut")
            db.refresh(record)
            serialized_record = serialize_company_expense(record)
            action = "company_expense_created_from_shortcut"
            resource_type = "company_expense"
            message = "\u516c\u53f8\u8bb0\u8d26\u6210\u529f"
        else:
            raise HTTPException(status_code=400, detail="\u8d26\u672c\u7c7b\u578b\u53ea\u80fd\u662f personal \u6216 company")

        write_audit_log(
            db,
            actor=current_user,
            action=action,
            resource_type=resource_type,
            resource_id=record.id,
            details=serialized_record,
        )
        commit_session(db, default_detail="Failed to record expense shortcut audit log")
        return {"success": True, "message": message, "book": book, "record": serialized_record}

    @router.get(
        "/company-expenses/summary",
        response_model=CompanyExpenseSummaryResponse,
        summary="Get current-month company expense summary",
    )
    def get_company_expense_summary(
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        today = date_type.today()
        month_start = today.replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        records = db.scalars(
            select(CompanyExpenseRecord).where(
                CompanyExpenseRecord.expense_date >= month_start,
                CompanyExpenseRecord.expense_date < next_month,
            )
        ).all()
        return {
            "month_total": sum(float(record.amount or 0) for record in records if record.approval_status != "rejected"),
            "pending_approval_total": sum(float(record.amount or 0) for record in records if record.approval_status == "pending"),
            "pending_reimbursement_total": sum(float(record.amount or 0) for record in records if record.reimbursement_status == "pending"),
            "month_record_count": len(records),
        }

    @router.get(
        "/company-expenses",
        response_model=list[CompanyExpenseResponse],
        summary="List company expenses",
    )
    def list_company_expenses(
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        records = db.scalars(
            select(CompanyExpenseRecord).order_by(
                CompanyExpenseRecord.expense_date.desc(),
                CompanyExpenseRecord.id.desc(),
            )
        ).all()
        return [serialize_company_expense(record) for record in records]

    @router.post(
        "/company-expenses",
        response_model=CompanyExpenseResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create a company expense",
    )
    def create_company_expense(
        payload: CompanyExpenseCreate,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        submitter_name = build_admin_user_public_name(current_user)
        record = CompanyExpenseRecord(
            expense_date=payload.expense_date,
            amount=payload.amount,
            category=payload.category,
            payment_type=payload.payment_type,
            payment_account=payload.payment_account,
            expense_scope=payload.expense_scope,
            description=payload.description,
            approval_status="approved",
            reimbursement_status="not_required",
            submitter_user_id=current_user.id,
            submitter_name=submitter_name,
        )
        db.add(record)
        commit_session(db, default_detail="Failed to create company expense")
        db.refresh(record)
        write_audit_log(
            db,
            actor=current_user,
            action="company_expense_created",
            resource_type="company_expense",
            resource_id=record.id,
            details=serialize_company_expense(record),
        )
        commit_session(db, default_detail="Failed to record company expense audit log")
        return serialize_company_expense(record)

    @router.get(
        "/company-expenses/{record_id}",
        response_model=CompanyExpenseResponse,
        summary="Get a company expense",
    )
    def get_company_expense(
        record_id: int,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        return serialize_company_expense(get_company_expense_or_404(db, record_id))

    @router.put(
        "/company-expenses/{record_id}",
        response_model=CompanyExpenseResponse,
        summary="Update a company expense",
    )
    def update_company_expense(
        record_id: int,
        payload: CompanyExpenseUpdate,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        record = get_company_expense_or_404(db, record_id)
        record.expense_date = payload.expense_date
        record.amount = payload.amount
        record.category = payload.category
        record.payment_type = payload.payment_type
        record.payment_account = payload.payment_account
        record.expense_scope = payload.expense_scope
        record.description = payload.description
        if payload.payment_type == "company":
            record.reimbursement_status = "not_required"
        elif record.reimbursement_status == "not_required":
            record.reimbursement_status = "pending"
        commit_session(db, default_detail="Failed to update company expense")
        db.refresh(record)
        write_audit_log(
            db,
            actor=current_user,
            action="company_expense_updated",
            resource_type="company_expense",
            resource_id=record.id,
            details=serialize_company_expense(record),
        )
        commit_session(db, default_detail="Failed to record company expense audit log")
        return serialize_company_expense(record)

    @router.patch(
        "/company-expenses/{record_id}/status",
        response_model=CompanyExpenseResponse,
        summary="Review or reimburse a company expense",
    )
    def update_company_expense_status(
        record_id: int,
        payload: CompanyExpenseStatusUpdate,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        record = get_company_expense_or_404(db, record_id)
        record.approval_status = payload.approval_status
        if payload.reimbursement_status is not None:
            record.reimbursement_status = payload.reimbursement_status
        if record.payment_type == "company":
            record.reimbursement_status = "not_required"
        record.reviewer_name = build_admin_user_public_name(current_user)
        record.reviewed_at = datetime.utcnow()
        commit_session(db, default_detail="Failed to update company expense status")
        db.refresh(record)
        write_audit_log(
            db,
            actor=current_user,
            action="company_expense_status_updated",
            resource_type="company_expense",
            resource_id=record.id,
            details=serialize_company_expense(record),
        )
        commit_session(db, default_detail="Failed to record company expense audit log")
        return serialize_company_expense(record)

    @router.post(
        "/company-expenses/{record_id}/attachment",
        response_model=CompanyExpenseResponse,
        summary="Upload or replace a company expense proof",
    )
    async def upload_company_expense_attachment(
        record_id: int,
        attachment: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        record = get_company_expense_or_404(db, record_id)
        await save_company_expense_attachment(record, attachment)
        commit_session(db, default_detail="Failed to upload company expense attachment")
        db.refresh(record)
        write_audit_log(
            db,
            actor=current_user,
            action="company_expense_attachment_uploaded",
            resource_type="company_expense",
            resource_id=record.id,
            details={"attachment_name": record.attachment_name},
        )
        commit_session(db, default_detail="Failed to record company expense attachment audit log")
        return serialize_company_expense(record)

    @router.get(
        "/company-expenses/{record_id}/attachment-file",
        summary="Download a protected company expense proof",
    )
    def get_company_expense_attachment_file(
        record_id: int,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        record = get_company_expense_or_404(db, record_id)
        if not record.attachment_path:
            raise HTTPException(status_code=404, detail="该消费记录没有凭证")
        file_path = Path(record.attachment_path).resolve()
        upload_dir = COMPANY_EXPENSE_UPLOAD_DIR.resolve()
        if file_path.parent != upload_dir or not file_path.is_file():
            raise HTTPException(status_code=404, detail="消费凭证文件不存在")
        return FileResponse(
            file_path,
            filename=record.attachment_name or file_path.name,
            media_type=mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
        )

    @router.delete(
        "/company-expenses/{record_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete a company expense",
    )
    def delete_company_expense(
        record_id: int,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        record = get_company_expense_or_404(db, record_id)
        backup_path = create_sqlite_backup("company-expense-delete")
        write_audit_log(
            db,
            actor=current_user,
            action="company_expense_deleted",
            resource_type="company_expense",
            resource_id=record.id,
            details={**serialize_company_expense(record), "backup_path": backup_path},
        )
        db.delete(record)
        commit_session(db, default_detail="Failed to delete company expense")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get(
        "/personal-expenses/summary",
        response_model=PersonalExpenseSummaryResponse,
        summary="Get current user's personal expense summary",
    )
    def get_personal_expense_summary(
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("viewer")),
    ):
        today = date_type.today()
        month_start = today.replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        records = db.scalars(
            select(PersonalExpenseRecord).where(
                PersonalExpenseRecord.owner_user_id == current_user.id,
                PersonalExpenseRecord.record_date >= month_start,
                PersonalExpenseRecord.record_date < next_month,
            )
        ).all()
        month_expense = sum(float(record.amount or 0) for record in records if record.transaction_type == "expense")
        month_income = sum(float(record.amount or 0) for record in records if record.transaction_type == "income")
        return {
            "month_expense": month_expense,
            "month_income": month_income,
            "month_balance": month_income - month_expense,
            "month_record_count": len(records),
        }

    @router.get(
        "/personal-expenses",
        response_model=list[PersonalExpenseResponse],
        summary="List current user's personal expenses",
    )
    def list_personal_expenses(
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("viewer")),
    ):
        records = db.scalars(
            select(PersonalExpenseRecord)
            .where(PersonalExpenseRecord.owner_user_id == current_user.id)
            .order_by(PersonalExpenseRecord.record_date.desc(), PersonalExpenseRecord.id.desc())
        ).all()
        return [serialize_personal_expense(record) for record in records]

    @router.post(
        "/personal-expenses",
        response_model=PersonalExpenseResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create a personal expense entry",
    )
    def create_personal_expense(
        payload: PersonalExpenseCreate,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("viewer")),
    ):
        record = PersonalExpenseRecord(
            record_date=payload.record_date,
            amount=payload.amount,
            transaction_type=payload.transaction_type,
            category=payload.category,
            payment_account=payload.payment_account,
            description=payload.description,
            owner_user_id=current_user.id,
            owner_name=build_admin_user_public_name(current_user),
        )
        db.add(record)
        commit_session(db, default_detail="Failed to create personal expense")
        db.refresh(record)
        write_audit_log(
            db,
            actor=current_user,
            action="personal_expense_created",
            resource_type="personal_expense",
            resource_id=record.id,
            details=serialize_personal_expense(record),
        )
        commit_session(db, default_detail="Failed to record personal expense audit log")
        return serialize_personal_expense(record)

    @router.get(
        "/personal-expenses/{record_id}",
        response_model=PersonalExpenseResponse,
        summary="Get a personal expense entry",
    )
    def get_personal_expense(
        record_id: int,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("viewer")),
    ):
        return serialize_personal_expense(get_personal_expense_or_404(db, record_id, current_user))

    @router.put(
        "/personal-expenses/{record_id}",
        response_model=PersonalExpenseResponse,
        summary="Update a personal expense entry",
    )
    def update_personal_expense(
        record_id: int,
        payload: PersonalExpenseUpdate,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("viewer")),
    ):
        record = get_personal_expense_or_404(db, record_id, current_user)
        record.record_date = payload.record_date
        record.amount = payload.amount
        record.transaction_type = payload.transaction_type
        record.category = payload.category
        record.payment_account = payload.payment_account
        record.description = payload.description
        commit_session(db, default_detail="Failed to update personal expense")
        db.refresh(record)
        write_audit_log(
            db,
            actor=current_user,
            action="personal_expense_updated",
            resource_type="personal_expense",
            resource_id=record.id,
            details=serialize_personal_expense(record),
        )
        commit_session(db, default_detail="Failed to record personal expense audit log")
        return serialize_personal_expense(record)

    @router.post(
        "/personal-expenses/{record_id}/attachment",
        response_model=PersonalExpenseResponse,
        summary="Upload a personal expense proof",
    )
    async def upload_personal_expense_attachment(
        record_id: int,
        attachment: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("viewer")),
    ):
        record = get_personal_expense_or_404(db, record_id, current_user)
        await save_personal_expense_attachment(record, attachment)
        commit_session(db, default_detail="Failed to upload personal expense attachment")
        db.refresh(record)
        write_audit_log(
            db,
            actor=current_user,
            action="personal_expense_attachment_uploaded",
            resource_type="personal_expense",
            resource_id=record.id,
            details={"attachment_name": record.attachment_name},
        )
        commit_session(db, default_detail="Failed to record personal expense attachment audit log")
        return serialize_personal_expense(record)

    @router.get(
        "/personal-expenses/{record_id}/attachment-file",
        summary="Download current user's personal expense proof",
    )
    def get_personal_expense_attachment_file(
        record_id: int,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("viewer")),
    ):
        record = get_personal_expense_or_404(db, record_id, current_user)
        if not record.attachment_path:
            raise HTTPException(status_code=404, detail="???????????")
        file_path = Path(record.attachment_path).resolve()
        upload_dir = PERSONAL_EXPENSE_UPLOAD_DIR.resolve()
        if file_path.parent != upload_dir or not file_path.is_file():
            raise HTTPException(status_code=404, detail="???????????")
        return FileResponse(
            file_path,
            filename=record.attachment_name or file_path.name,
            media_type=mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
        )

    @router.delete(
        "/personal-expenses/{record_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete a personal expense entry",
    )
    def delete_personal_expense(
        record_id: int,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("viewer")),
    ):
        record = get_personal_expense_or_404(db, record_id, current_user)
        backup_path = create_sqlite_backup("personal-expense-delete")
        write_audit_log(
            db,
            actor=current_user,
            action="personal_expense_deleted",
            resource_type="personal_expense",
            resource_id=record.id,
            details={**serialize_personal_expense(record), "backup_path": backup_path},
        )
        db.delete(record)
        commit_session(db, default_detail="Failed to delete personal expense")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
