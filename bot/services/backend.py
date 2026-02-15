"""Thin httpx wrapper for internal backend API calls."""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BASE_URL = f"{settings.backend_url}/api/internal/bot"


async def upsert_user(
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> dict | None:
    """Register/update a user and return user data with internal ID."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{BASE_URL}/upsert-user",
            json={
                "telegram_id": telegram_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
            },
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning("upsert_user failed: %s", resp.text)
        return None


async def get_user_deals(user_id: int) -> list[dict]:
    """Fetch deals for both roles and merge them."""
    all_deals: dict[int, dict] = {}
    async with httpx.AsyncClient(timeout=10) as client:
        for role in ("advertiser", "owner"):
            resp = await client.get(
                f"{BASE_URL}/deals",
                params={"user_id": user_id, "role": role},
            )
            if resp.status_code == 200:
                for d in resp.json():
                    all_deals[d["id"]] = d
    return sorted(all_deals.values(), key=lambda d: d["id"], reverse=True)


async def get_deal_detail(deal_id: int, user_id: int) -> dict | None:
    """Return deal detail with messages and available_actions."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BASE_URL}/deals/{deal_id}",
            params={"user_id": user_id},
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning("get_deal_detail failed: %s", resp.text)
        return None


async def transition_deal(deal_id: int, user_id: int, action: str) -> dict | None:
    """Trigger a deal state transition.

    Returns the deal dict on success, None on failure.
    On 400 errors, raises ValueError with the backend detail so callers
    can show a meaningful message.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{BASE_URL}/deals/{deal_id}/transition",
            json={"user_id": user_id, "action": action},
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning("transition_deal failed: %s", resp.text)
        if resp.status_code == 400:
            detail = ""
            try:
                detail = resp.json().get("detail", "")
            except Exception:
                pass
            if detail:
                raise ValueError(detail)
        return None


async def send_deal_message(
    deal_id: int, user_id: int, text: str,
    media_items: list[dict] | None = None,
) -> dict | None:
    """Send a deal message on behalf of a user."""
    payload: dict = {"user_id": user_id, "text": text}
    if media_items:
        payload["media_items"] = media_items
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{BASE_URL}/deals/{deal_id}/messages",
            json=payload,
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning("send_deal_message failed: %s", resp.text)
        return None


async def update_deal_brief(
    deal_id: int,
    user_id: int,
    brief: str | None = None,
    publish_from: str | None = None,
    publish_to: str | None = None,
) -> dict | None:
    """Update deal brief fields (DRAFT only)."""
    payload: dict = {"user_id": user_id}
    if brief is not None:
        payload["brief"] = brief
    if publish_from is not None:
        payload["publish_from"] = publish_from
    if publish_to is not None:
        payload["publish_to"] = publish_to
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.patch(
            f"{BASE_URL}/deals/{deal_id}",
            json=payload,
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning("update_deal_brief failed: %s", resp.text)
        return None


async def propose_amendment(
    deal_id: int,
    user_id: int,
    proposed_price: str | None = None,
    proposed_publish_date: str | None = None,
    proposed_description: str | None = None,
) -> dict | None:
    """Owner proposes changes to a deal."""
    payload: dict = {"user_id": user_id}
    if proposed_price is not None:
        payload["proposed_price"] = proposed_price
    if proposed_publish_date is not None:
        payload["proposed_publish_date"] = proposed_publish_date
    if proposed_description is not None:
        payload["proposed_description"] = proposed_description
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{BASE_URL}/deals/{deal_id}/amendments",
            json=payload,
        )
        if resp.status_code in (200, 201):
            return resp.json()
        logger.warning("propose_amendment failed: %s", resp.text)
        return None


async def resolve_amendment(
    deal_id: int,
    amendment_id: int,
    user_id: int,
    action: str,
) -> dict | None:
    """Advertiser accepts or rejects an amendment."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{BASE_URL}/deals/{deal_id}/amendments/{amendment_id}/resolve",
            json={"user_id": user_id, "action": action},
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning("resolve_amendment failed: %s", resp.text)
        return None


async def submit_creative(
    deal_id: int,
    user_id: int,
    text: str,
    entities_json: str | None = None,
    media_items: list[dict] | None = None,
) -> dict | None:
    """Owner submits a creative for review."""
    payload: dict = {"user_id": user_id, "text": text}
    if entities_json is not None:
        payload["entities_json"] = entities_json
    if media_items:
        payload["media_items"] = media_items
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{BASE_URL}/deals/{deal_id}/creative",
            json=payload,
        )
        if resp.status_code in (200, 201):
            return resp.json()
        logger.warning("submit_creative failed: %s", resp.text)
        return None


async def approve_creative(deal_id: int, user_id: int) -> dict | None:
    """Advertiser approves the current creative."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{BASE_URL}/deals/{deal_id}/creative/approve",
            json={"user_id": user_id, "action": "approve_creative"},
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning("approve_creative failed: %s", resp.text)
        return None


async def request_creative_changes(
    deal_id: int, user_id: int, feedback: str,
) -> dict | None:
    """Advertiser requests changes to the creative."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{BASE_URL}/deals/{deal_id}/creative/request-changes",
            json={"user_id": user_id, "feedback": feedback},
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning("request_creative_changes failed: %s", resp.text)
        return None


async def schedule_post(
    deal_id: int, user_id: int, scheduled_at: str,
) -> dict | None:
    """Owner schedules a post for the deal."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{BASE_URL}/deals/{deal_id}/schedule",
            json={"user_id": user_id, "scheduled_at": scheduled_at},
        )
        if resp.status_code in (200, 201):
            return resp.json()
        logger.warning("schedule_post failed: %s", resp.text)
        return None
