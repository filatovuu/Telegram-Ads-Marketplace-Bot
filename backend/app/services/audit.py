"""Fire-and-forget audit logging service."""

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def log_audit(
    db: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    user_id: int | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Write an audit log entry. Exceptions are caught and logged."""
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=json.dumps(details, default=str) if details else None,
            ip_address=ip_address,
        )
        db.add(entry)
        await db.flush()
    except Exception:
        logger.exception("Failed to write audit log: %s %s/%s", action, entity_type, entity_id)
