import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.app.core.logging import logger
from backend.app.db.sqlite import db


class AuditService:
    """Minimal internal audit service for recording security and mutation events."""

    def log_event(
        self,
        username: str,
        action: str,
        resource_type: str,
        resource_id: str,
        status: str,
        user_id: Optional[str] = None,
        details: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> str:
        """
        Records an audit event safely into the SQLite audit_logs table.
        Does NOT log passwords, session tokens, or sensitive payload data.
        """
        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO audit_logs (
                        id, user_id, username, action, resource_type,
                        resource_id, status, details, ip_address, request_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        event_id,
                        user_id,
                        username,
                        action,
                        resource_type,
                        resource_id,
                        status,
                        details,
                        ip_address,
                        request_id,
                        now,
                    ),
                )
                conn.commit()
            logger.info(
                f"Audit event: user='{username}' action='{action}' resource='{resource_type}/{resource_id}' status='{status}'",
                extra={"request_id": request_id},
            )
        except Exception as exc:
            # Audit logging must not crash primary operations, but must log failure server-side
            logger.error(f"Failed to record audit event: {exc}", extra={"request_id": request_id})

        return event_id


audit_service = AuditService()
