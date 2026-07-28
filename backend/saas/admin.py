"""Private-beta owner dashboard.

Every endpoint verifies the caller's database-backed membership. Browser claims
and request payloads are never used to determine administrative access.
"""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from .auth import CurrentUser, get_current_user, get_user_client
from .invites import BetaInviteCreate, create_beta_invite, revoke_beta_invite


router = APIRouter(prefix="/admin", tags=["Private beta administration"])


class FeedbackUpdate(BaseModel):
    status: Literal["open", "reviewing", "resolved"]
    owner_notes: str | None = Field(default=None, max_length=5000)


class AccountUpdate(BaseModel):
    active: bool


class RetryRequest(BaseModel):
    event_id: str


def _one(response):
    data = response.data
    if isinstance(data, list):
        return data[0] if data else {}
    return data or {}


def require_admin(user: CurrentUser = Depends(get_current_user)):
    client = get_user_client(user)
    membership = _one(
        client.table("private_beta_memberships")
        .select("role,active")
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


def _audit(client, user: CurrentUser, action: str, target_type: str, target_id: str, metadata=None):
    client.table("admin_audit_log").insert(
        {
            "admin_user_id": user.id,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "metadata": metadata or {},
        }
    ).execute()


@router.get("/overview")
def overview(
    search: str = Query(default="", max_length=120),
    feedback_status: str | None = Query(default=None, pattern="^(open|reviewing|resolved)$"),
    severity: str | None = Query(default=None, pattern="^(low|medium|high|critical)$"),
    user: CurrentUser = Depends(get_current_user),
):
    client = require_admin(user)
    result = _one(
        client.rpc(
            "beta_admin_dashboard",
            {
                "p_search": search.strip(),
                "p_feedback_status": feedback_status,
                "p_severity": severity,
            },
        ).execute()
    )
    return result


@router.patch("/feedback/{feedback_id}")
def update_feedback(
    feedback_id: str,
    payload: FeedbackUpdate,
    user: CurrentUser = Depends(get_current_user),
):
    client = require_admin(user)
    row = _one(
        client.table("beta_feedback")
        .update(
            {
                "status": payload.status,
                "owner_notes": payload.owner_notes.strip() if payload.owner_notes else None,
                "resolved_at": datetime.now(timezone.utc).isoformat() if payload.status == "resolved" else None,
            }
        )
        .eq("id", feedback_id)
        .execute()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Feedback not found.")
    _audit(client, user, "feedback.status_updated", "beta_feedback", feedback_id, {"status": payload.status})
    return row


@router.patch("/testers/{user_id}/account")
def update_beta_account(
    user_id: str,
    payload: AccountUpdate,
    user: CurrentUser = Depends(get_current_user),
):
    client = require_admin(user)
    if user_id == user.id and not payload.active:
        raise HTTPException(status_code=409, detail="You cannot disable your own owner account.")
    target = _one(
        client.table("private_beta_memberships")
        .select("user_id,role,active")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not target:
        raise HTTPException(status_code=404, detail="Beta account not found.")
    if target.get("role") == "OWNER" and not payload.active:
        raise HTTPException(status_code=409, detail="Owner accounts cannot be disabled here.")
    row = _one(
        client.table("private_beta_memberships")
        .update({"active": payload.active})
        .eq("user_id", user_id)
        .execute()
    )
    _audit(client, user, "beta_account.enabled" if payload.active else "beta_account.disabled", "user", user_id)
    return row


@router.get("/testers/{user_id}/activity")
def user_activity(user_id: str, user: CurrentUser = Depends(get_current_user)):
    client = require_admin(user)
    result = _one(client.rpc("beta_admin_user_activity", {"p_user_id": user_id}).execute())
    _audit(client, user, "user.activity_viewed", "user", user_id)
    return result


@router.post("/jobs/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_failed_job(payload: RetryRequest, user: CurrentUser = Depends(get_current_user)):
    client = require_admin(user)
    event = _one(
        client.table("beta_monitoring_events")
        .select("id,event_type,severity,context")
        .eq("id", payload.event_id)
        .maybe_single()
        .execute()
    )
    retryable = {"scheduler_failure", "failed_market_data"}
    if not event or event.get("event_type") not in retryable:
        raise HTTPException(status_code=422, detail="Only failed non-destructive jobs can be retried.")
    row = _one(
        client.table("admin_job_retries")
        .insert({"event_id": payload.event_id, "requested_by": user.id})
        .execute()
    )
    _audit(client, user, "job.retry_requested", "monitoring_event", payload.event_id)
    return row


@router.post("/invites", status_code=status.HTTP_201_CREATED)
def admin_create_invite(payload: BetaInviteCreate, user: CurrentUser = Depends(get_current_user)):
    require_admin(user)
    result = create_beta_invite(payload, _NoStoreResponse(), user)
    client = get_user_client(user)
    _audit(client, user, "invite.created", "beta_invite", result["id"])
    return result


@router.post("/invites/{invite_id}/revoke")
def admin_revoke_invite(invite_id: str, user: CurrentUser = Depends(get_current_user)):
    require_admin(user)
    result = revoke_beta_invite(invite_id, user)
    _audit(get_user_client(user), user, "invite.revoked", "beta_invite", invite_id)
    return result


class _NoStoreResponse:
    def __init__(self):
        self.headers: dict[str, str] = {}
