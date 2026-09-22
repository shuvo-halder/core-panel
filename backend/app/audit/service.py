import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.logging import logger
from backend.app.db.sqlite import db

SENSITIVE_FIELD_REDACT_REGEX = re.compile(
    r'(?i)["\']?(password|token|secret|key|cookie|authorization|auth_token|session_id|credential)[s]?["\']?\s*[:=]\s*(?:"[^"]*"|\'[^\']*\'|[^\s,;}"\']+)'
)


def redact_sensitive_text(text: Optional[str]) -> Optional[str]:
    """Redacts any sensitive credential patterns from audit details text."""
    if not text:
        return text
    return SENSITIVE_FIELD_REDACT_REGEX.sub(r"\1=[REDACTED]", text)


class AuditService:
    """Internal audit service for recording and retrieving security and mutation events."""

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
        clean_details = redact_sensitive_text(details)

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
                        clean_details,
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

    def query_events(
        self,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Queries application audit events with pagination and filters.
        Enforces field redaction so credentials or tokens are never returned.
        """
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        offset = (page - 1) * page_size

        where_clauses: List[str] = []
        params: List[Any] = []

        if user_id:
            where_clauses.append("user_id = ?")
            params.append(user_id)
        if username:
            where_clauses.append("username = ?")
            params.append(username)
        if action:
            where_clauses.append("action = ?")
            params.append(action)
        if resource_type:
            where_clauses.append("resource_type = ?")
            params.append(resource_type)
        if status:
            where_clauses.append("status = ?")
            params.append(status.upper())
        if since:
            where_clauses.append("created_at >= ?")
            params.append(since)
        if until:
            where_clauses.append("created_at <= ?")
            params.append(until)
        if search:
            clean_search = f"%{search.strip()}%"
            where_clauses.append(
                "(username LIKE ? OR action LIKE ? OR resource_type LIKE ? OR resource_id LIKE ? OR details LIKE ?)"
            )
            params.extend([clean_search] * 5)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Count total matching rows
            count_query = f"SELECT COUNT(*) AS total FROM audit_logs {where_sql}"
            cursor.execute(count_query, params)
            count_row = cursor.fetchone()
            total = count_row["total"] if count_row else 0

            # Query paginated rows
            select_query = f"""
                SELECT id, user_id, username, action, resource_type,
                       resource_id, status, details, ip_address, request_id, created_at
                FROM audit_logs
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            cursor.execute(select_query, params + [page_size, offset])
            rows = cursor.fetchall()

            events: List[Dict[str, Any]] = []
            for row in rows:
                events.append({
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "username": row["username"],
                    "action": row["action"],
                    "resource_type": row["resource_type"],
                    "resource_id": row["resource_id"],
                    "status": row["status"],
                    "details": redact_sensitive_text(row["details"]),
                    "ip_address": row["ip_address"],
                    "request_id": row["request_id"],
                    "created_at": row["created_at"],
                })

            return events, total


audit_service = AuditService()

