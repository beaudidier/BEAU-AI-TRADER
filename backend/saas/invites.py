"""Owner-managed, hashed invite codes for private-beta self-registration."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from .auth import CurrentUser, get_current_user, get_user_client
from .config import get_settings


router = APIRouter(prefix="/me/beta-invites", tags=["Private beta invites"])


class BetaInviteCreate(BaseModel):
    expires_in_days: int = Field(default=7, ge=1, le=30)
    max_uses: int = Field(default=1, ge=1, le=100)
    label: str | None = Field(default=None, max_length=120)


class BetaInviteSummary(BaseModel):
    id: str
    status: Literal["active", "used", "revoked", "expired"]
    created_at: str
    expires_at: str
    max_uses: int
    use_count: int
    remaining_uses: int
    label: str | None = None


class BetaInviteCreated(BetaInviteSummary):
    invite_url: str


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _one(response):
    data = response.data
    if isinstance(data, list):
        return data[0] if data else {}
    return data or {}


def _require_admin(user: CurrentUser):
    client = get_user_client(user)
    membership = _one(
        client.table("private_beta_memberships")
        .select("role, active")
        .eq("user_id", user.id)
        .maybe_single()
        .execute()
    )
    if (
        not membership.get("active")
        or membership.get("role") not in {"OWNER", "ADMIN"}
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner or administrator access is required.",
        )
    return client


def _serialize_invite(row: dict) -> dict:
    expires_at = datetime.fromisoformat(
        str(row["expires_at"]).replace("Z", "+00:00")
    )
    invite_status = row["status"]
    if (
        invite_status == "active"
        and expires_at <= datetime.now(timezone.utc)
    ):
        invite_status = "expired"
    use_count = int(row["use_count"])
    max_uses = int(row["max_uses"])
    return {
        "id": str(row["id"]),
        "status": invite_status,
        "created_at": str(row["created_at"]),
        "expires_at": str(row["expires_at"]),
        "max_uses": max_uses,
        "use_count": use_count,
        "remaining_uses": max(0, max_uses - use_count),
        "label": row.get("label"),
    }


@router.get("", response_model=list[BetaInviteSummary])
def list_beta_invites(user: CurrentUser = Depends(get_current_user)):
    client = _require_admin(user)
    rows = (
        client.table("beta_invites")
        .select(
            "id,status,created_at,expires_at,max_uses,use_count,label"
        )
        .order("created_at", desc=True)
        .limit(100)
        .execute()
        .data
        or []
    )
    return [_serialize_invite(row) for row in rows]


@router.post(
    "",
    response_model=BetaInviteCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_beta_invite(
    payload: BetaInviteCreate,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    client = _require_admin(user)
    clear_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=payload.expires_in_days
    )
    row = _one(
        client.table("beta_invites")
        .insert(
            {
                "token_hash": hash_invite_token(clear_token),
                "expires_at": expires_at.isoformat(),
                "max_uses": payload.max_uses,
                "created_by": user.id,
                "label": payload.label.strip() if payload.label else None,
            }
        )
        .execute()
    )
    result = _serialize_invite(row)
    frontend_url = get_settings().frontend_app_url.rstrip("/")
    result["invite_url"] = f"{frontend_url}/invite/{clear_token}"
    return result


@router.post("/{invite_id}/revoke", response_model=BetaInviteSummary)
def revoke_beta_invite(
    invite_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    client = _require_admin(user)
    existing = _one(
        client.table("beta_invites")
        .select(
            "id,status,created_at,expires_at,max_uses,use_count,label"
        )
        .eq("id", invite_id)
        .maybe_single()
        .execute()
    )
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found.",
        )
    if existing["status"] == "active":
        existing = _one(
            client.table("beta_invites")
            .update({"status": "revoked"})
            .eq("id", invite_id)
            .execute()
        )
    return _serialize_invite(existing)
