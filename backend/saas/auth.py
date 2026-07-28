from dataclasses import dataclass

from fastapi import Header, HTTPException, status
try:
    import jwt
    from supabase import Client, create_client
    from supabase_auth.errors import AuthApiError
    from postgrest.exceptions import APIError
except ImportError:
    jwt = None
    Client = object
    create_client = None
    AuthApiError = ValueError
    APIError = ValueError

from .config import get_settings


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None
    access_token: str


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer access token")
    return authorization.removeprefix("Bearer ").strip()


def _supabase_client(access_token: str | None = None) -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Supabase is not configured")
    if create_client is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Supabase backend dependencies are not installed")
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    if access_token:
        client.postgrest.auth(access_token)
    return client


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    """Verify the Supabase access token and return only its authenticated identity."""

    access_token = _extract_bearer_token(authorization)
    settings = get_settings()
    try:
        if settings.supabase_jwt_secret:
            if jwt is None:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="JWT verification dependency is not installed")
            payload = jwt.decode(access_token, settings.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated")
            user_id = payload.get("sub")
            if not user_id:
                raise jwt.InvalidTokenError("Token has no subject")
            current_user = CurrentUser(
                id=user_id,
                email=payload.get("email"),
                access_token=access_token,
            )
            _require_private_beta_access(current_user)
            return current_user

        user = _supabase_client().auth.get_user(access_token).user
        if not user:
            raise ValueError("Supabase did not return a user")
        current_user = CurrentUser(
            id=user.id,
            email=user.email,
            access_token=access_token,
        )
        _require_private_beta_access(current_user)
        return current_user
    except ((jwt.PyJWTError if jwt else ValueError), ValueError, AuthApiError) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token") from error


def get_user_client(user: CurrentUser) -> Client:
    """Create a database client scoped to the verified caller JWT so RLS applies."""

    return _supabase_client(user.access_token)


def _require_private_beta_access(user: CurrentUser) -> None:
    """Restrict production access to active invited members when enabled."""

    if not getattr(get_settings(), "private_beta_enforced", False):
        return
    try:
        membership = (
            _supabase_client(user.access_token)
            .table("private_beta_memberships")
            .select("active")
            .eq("user_id", user.id)
            .eq("active", True)
            .maybe_single()
            .execute()
        )
    except APIError as error:
        if getattr(error, "code", None) != "PGRST116":
            raise
        membership = None
    if not membership or not membership.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This private beta is available to invited testers only.",
        )
