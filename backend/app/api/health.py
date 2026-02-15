from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


@router.get("/config/public")
async def public_config() -> dict:
    """Public platform configuration (fees, limits, etc.)."""
    return {
        "platform_fee_percent": settings.platform_fee_percent,
        "escrow_gas_ton": 0.1,
        "min_price_ton": 0.5,
        "ton_network": settings.ton_network,
    }
