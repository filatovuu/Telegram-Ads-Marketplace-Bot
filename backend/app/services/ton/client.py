"""Async HTTP client for Toncenter API v3."""

import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings

logger = logging.getLogger(__name__)

# Suppress noisy httpx request logging (logs every HTTP request at INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)


class TonClient:
    """Thin async wrapper around Toncenter REST API."""

    def __init__(self) -> None:
        base = settings.ton_api_base_url
        if settings.ton_network == "testnet" and "toncenter.com" in base:
            base = base.replace("toncenter.com", "testnet.toncenter.com")
        self.base_url = base.rstrip("/")
        self.api_key = settings.ton_api_key

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Accept": "application/json"}
        if self.api_key:
            h["X-API-Key"] = self.api_key
        return h

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.5, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        """Execute HTTP request with tenacity retry."""
        req_timeout = kwargs.pop("timeout", 15)
        async with httpx.AsyncClient(timeout=req_timeout) as client:
            if method == "GET":
                resp = await client.get(url, **kwargs)
            else:
                resp = await client.post(url, **kwargs)
        resp.raise_for_status()
        return resp

    async def get_account_state(self, address: str) -> dict:
        """Get account state (balance, code, data) for an address."""
        resp = await self._request(
            "GET",
            f"{self.base_url}/account",
            params={"address": address},
            headers=self._headers(),
        )
        return resp.json()

    async def get_transactions(
        self, address: str, limit: int = 10, offset: int = 0,
    ) -> list[dict]:
        """Get recent transactions for an address."""
        resp = await self._request(
            "GET",
            f"{self.base_url}/transactions",
            params={"account": address, "limit": limit, "offset": offset},
            headers=self._headers(),
        )
        data = resp.json()
        return data.get("transactions", [])

    async def run_get_method(
        self, address: str, method: str, stack: list | None = None,
    ) -> dict:
        """Run a get method on a smart contract."""
        resp = await self._request(
            "POST",
            f"{self.base_url}/runGetMethod",
            json={
                "address": address,
                "method": method,
                "stack": stack or [],
            },
            headers=self._headers(),
        )
        return resp.json()

    async def send_boc(self, boc: str) -> dict:
        """Send a serialized BOC (base64) to the network."""
        resp = await self._request(
            "POST",
            f"{self.base_url}/message",
            json={"boc": boc},
            headers=self._headers(),
            timeout=30,
        )
        return resp.json()
