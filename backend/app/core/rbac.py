"""Role-based access control dependencies."""

from fastapi import Depends, HTTPException, status

from app.core.security import get_current_user
from app.models.user import User


def require_role(role: str):
    """Return a FastAPI dependency that enforces the user's active_role."""

    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.active_role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires the '{role}' role",
            )
        return user

    return _check


require_owner = require_role("owner")
require_advertiser = require_role("advertiser")
