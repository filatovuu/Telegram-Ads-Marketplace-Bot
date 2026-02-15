import hashlib
import hmac
import json
from urllib.parse import quote, urlencode

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.security import verify_init_data


def _build_init_data(user_data: dict, bot_token: str) -> str:
    """Build a valid Telegram initData string with correct HMAC signature."""
    import time

    user_json = json.dumps(user_data, separators=(",", ":"))
    params = {
        "user": user_json,
        "auth_date": str(int(time.time())),
        "query_id": "test_query",
    }
    # Build data-check-string
    data_check_pairs = sorted(params.items(), key=lambda x: x[0])
    data_check_string = "\n".join(f"{k}={v}" for k, v in data_check_pairs)

    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    computed_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    params["hash"] = computed_hash
    return urlencode(params, quote_via=quote)


class TestVerifyInitData:
    def test_valid_signature(self):
        user_data = {"id": 123456, "first_name": "Test", "username": "testuser"}
        init_data = _build_init_data(user_data, settings.bot_token)
        result = verify_init_data(init_data, settings.bot_token)
        assert result["user"]["id"] == 123456
        assert result["user"]["username"] == "testuser"

    def test_missing_hash(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            verify_init_data("user=%7B%7D&auth_date=123", settings.bot_token)
        assert exc_info.value.status_code == 401

    def test_invalid_hash(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            verify_init_data(
                "user=%7B%7D&auth_date=123&hash=invalidhash", settings.bot_token
            )
        assert exc_info.value.status_code == 401


class TestAuthEndpoint:
    @pytest.mark.asyncio
    async def test_auth_telegram_invalid_data(self, client: AsyncClient):
        response = await client.post(
            "/api/auth/telegram",
            json={"init_data": "invalid_data"},
        )
        assert response.status_code == 401


class TestMeEndpoints:
    @pytest.mark.asyncio
    async def test_me_unauthorized(self, client: AsyncClient):
        response = await client.get("/api/me")
        assert response.status_code == 403  # No Bearer token

    @pytest.mark.asyncio
    async def test_me_invalid_token(self, client: AsyncClient):
        response = await client.get(
            "/api/me", headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_role_switch_unauthorized(self, client: AsyncClient):
        response = await client.post(
            "/api/me/role",
            json={"role": "owner"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_role_switch_invalid_role(self, client: AsyncClient):
        """Validation should reject invalid role values."""
        response = await client.post(
            "/api/me/role",
            json={"role": "admin"},
            headers={"Authorization": "Bearer dummy"},
        )
        assert response.status_code in (401, 422)
