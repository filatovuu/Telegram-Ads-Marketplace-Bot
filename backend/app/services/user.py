from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_user_by_telegram_id(db: AsyncSession, telegram_id: int) -> User | None:
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def upsert_user(
    db: AsyncSession,
    *,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    photo_url: str | None = None,
    language_code: str | None = None,
    timezone: str | None = None,
) -> User:
    user = await get_user_by_telegram_id(db, telegram_id)
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            photo_url=photo_url,
            locale=language_code if language_code in ("en", "ru") else "en",
            timezone=timezone or "UTC",
        )
        db.add(user)
    else:
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        if photo_url is not None:
            user.photo_url = photo_url
        if timezone is not None:
            user.timezone = timezone

    await db.commit()
    await db.refresh(user)
    return user


async def switch_user_role(db: AsyncSession, user: User, role: str) -> User:
    user.active_role = role
    await db.commit()
    await db.refresh(user)
    return user
