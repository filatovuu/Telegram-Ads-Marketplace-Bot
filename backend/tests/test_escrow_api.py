"""Integration tests for escrow API endpoints."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import get_current_user
from app.main import app
from app.models.user import User


def _make_user(id: int = 1, role: str = "advertiser") -> User:
    user = User(
        telegram_id=111,
        username="testuser",
        first_name="Test",
        last_name="User",
        locale="en",
        active_role=role,
    )
    object.__setattr__(user, "id", id)
    return user


def _mock_deal(
    id=1, advertiser_id=1, owner_id=2, status="OWNER_ACCEPTED",
):
    deal = MagicMock()
    deal.id = id
    deal.listing_id = 1
    deal.campaign_id = None
    deal.advertiser_id = advertiser_id
    deal.owner_id = owner_id
    deal.status = status
    deal.price = Decimal("5.0")
    deal.currency = "TON"
    deal.escrow_address = None
    deal.brief = "test brief"
    deal.publish_date = None
    deal.description = None
    deal.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    deal.updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    deal.last_activity_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    deal.listing = None
    deal.advertiser = _make_user(id=1)
    deal.owner = _make_user(id=2, role="owner")
    return deal


def _mock_escrow(deal_id=1, on_chain_state="init"):
    escrow = MagicMock()
    escrow.id = 1
    escrow.deal_id = deal_id
    escrow.contract_address = "EQTest123"
    escrow.advertiser_address = "EQAdv"
    escrow.owner_address = "EQOwn"
    escrow.platform_address = "EQPlat"
    escrow.amount = Decimal("5.0")
    escrow.deadline = None
    escrow.on_chain_state = on_chain_state
    escrow.deploy_tx_hash = None
    escrow.deposit_tx_hash = None
    escrow.release_tx_hash = None
    escrow.refund_tx_hash = None
    escrow.funded_at = None
    escrow.released_at = None
    escrow.refunded_at = None
    return escrow


class TestCreateEscrow:
    @pytest.mark.asyncio
    async def test_unauthenticated(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/api/escrow/deals/1/create",
                json={"advertiser_address": "EQAdv", "owner_address": "EQOwn"},
            )
            # Should fail without auth token
            assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_only_advertiser_can_create(self):
        """Owner should not be able to create an escrow."""
        owner = _make_user(id=2, role="owner")
        deal = _mock_deal(advertiser_id=1, owner_id=2)

        app.dependency_overrides[get_current_user] = lambda: owner
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                with patch("app.services.deal.get_deal", new_callable=AsyncMock, return_value=deal):
                    resp = await client.post(
                        "/api/escrow/deals/1/create",
                        json={"advertiser_address": "EQAdv", "owner_address": "EQOwn"},
                    )
                    assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()


class TestGetEscrowStatus:
    @pytest.mark.asyncio
    async def test_not_found(self):
        user = _make_user()
        deal = _mock_deal()

        app.dependency_overrides[get_current_user] = lambda: user
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                with (
                    patch("app.services.deal.get_deal", new_callable=AsyncMock, return_value=deal),
                    patch(
                        "app.api.escrow.escrow_service.get_escrow_for_deal",
                        new_callable=AsyncMock,
                        return_value=None,
                    ),
                ):
                    resp = await client.get("/api/escrow/deals/1")
                    assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestConfirmDeposit:
    @pytest.mark.asyncio
    async def test_no_escrow(self):
        user = _make_user()
        deal = _mock_deal()

        app.dependency_overrides[get_current_user] = lambda: user
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                with (
                    patch("app.services.deal.get_deal", new_callable=AsyncMock, return_value=deal),
                    patch(
                        "app.api.escrow.escrow_service.get_escrow_for_deal",
                        new_callable=AsyncMock,
                        return_value=None,
                    ),
                ):
                    resp = await client.post("/api/escrow/deals/1/confirm-deposit")
                    assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()
