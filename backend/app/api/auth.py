from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import AuthResponse, TelegramAuthRequest
from app.core.config import settings
from app.core.deps import get_db
from app.core.rate_limit import limiter
from app.core.security import create_access_token, verify_init_data
from app.services.user import upsert_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/telegram", response_model=AuthResponse)
@limiter.limit(settings.rate_limit_auth)
async def auth_telegram(
    request: Request,
    body: TelegramAuthRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Authenticate via Telegram Mini App initData.

    1. Verify initData HMAC signature.
    2. Extract user info.
    3. Upsert User in DB.
    4. Return JWT + user data.
    """
    parsed = verify_init_data(body.init_data, settings.bot_token)
    user_info = parsed.get("user", {})

    user = await upsert_user(
        db,
        telegram_id=user_info.get("id"),
        username=user_info.get("username"),
        first_name=user_info.get("first_name"),
        last_name=user_info.get("last_name"),
        photo_url=user_info.get("photo_url"),
        language_code=user_info.get("language_code"),
        timezone=body.timezone,
    )

    access_token = create_access_token(data={"sub": str(user.id)})
    return AuthResponse(access_token=access_token, user=user)
