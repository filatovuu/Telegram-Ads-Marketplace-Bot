import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, unquote

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db
from app.models.user import User
from app.services.user import get_user_by_id

bearer_scheme = HTTPBearer()


def verify_init_data(init_data: str, bot_token: str) -> dict:
    """Verify Telegram Mini App initData using HMAC-SHA256.

    Follows the official Telegram verification algorithm:
    1. Parse the init_data query string.
    2. Sort all key-value pairs alphabetically by key, excluding 'hash'.
    3. Create a data-check-string by joining them with newlines.
    4. Compute HMAC-SHA256 of the data-check-string using a secret key
       derived from the bot token.
    5. Compare with the provided hash.

    Returns the parsed data as a dict on success, raises HTTPException on failure.
    """
    parsed = parse_qs(init_data, keep_blank_values=True)
    # parse_qs returns lists; flatten to single values
    flat: dict[str, str] = {k: v[0] for k, v in parsed.items()}

    received_hash = flat.pop("hash", None)
    if not received_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing hash in initData",
        )

    # Build the data-check-string
    data_check_pairs = sorted(flat.items(), key=lambda x: x[0])
    data_check_string = "\n".join(f"{k}={v}" for k, v in data_check_pairs)

    # Compute secret key: HMAC-SHA256 of bot_token with "WebAppData" as key
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    # Compute hash
    computed_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid initData signature",
        )

    # Replay protection: reject initData older than max_age
    auth_date_str = flat.get("auth_date")
    if auth_date_str:
        try:
            auth_ts = int(auth_date_str)
            now_ts = int(datetime.now(timezone.utc).timestamp())
            if now_ts - auth_ts > settings.init_data_max_age_seconds:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="initData expired (replay protection)",
                )
        except ValueError:
            pass  # non-numeric auth_date — skip check

    # Parse the user field (JSON-encoded)
    result: dict[str, Any] = dict(flat)
    if "user" in result:
        result["user"] = json.loads(unquote(result["user"]))

    return result


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency: extract and return the current User from the Bearer token."""
    payload = decode_access_token(credentials.credentials)
    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing subject",
        )

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        ) from exc

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user
