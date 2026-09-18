import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.app.auth.hashing import hasher
from backend.app.auth.models import (
    RoleCreate,
    RoleRead,
    RoleUpdate,
    UserCreate,
    UserRead,
    UserUpdate,
)
from backend.app.core.config import settings
from backend.app.core.errors import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    UnauthorizedError,
)
from backend.app.core.logging import logger
from backend.app.db.sqlite import db


class AuthService:
    """Authentication and RBAC business logic and repository service."""

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def bootstrap_admin_if_configured(self) -> None:
        """Idempotently bootstrap initial administrator if configured via environment variables."""
        username = settings.BOOTSTRAP_ADMIN_USERNAME
        password = settings.BOOTSTRAP_ADMIN_PASSWORD
        email = settings.BOOTSTRAP_ADMIN_EMAIL

        if not username or not password:
            return

        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Check if any admin role is already assigned to an existing user
            cursor.execute("""
                SELECT u.id FROM users u
                JOIN user_roles ur ON u.id = ur.user_id
                JOIN roles r ON ur.role_id = r.id
                WHERE r.name = 'admin'
            """)
            if cursor.fetchone():
                logger.info("Admin user already exists. Skipping bootstrap.")
                return

            # Check if username already exists
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                logger.info("User matching bootstrap username already exists. Skipping bootstrap.")
                return

            user_id = f"usr_{uuid.uuid4().hex[:12]}"
            pw_hash = hasher.hash(password)
            now = self._now()

            cursor.execute(
                """
                INSERT INTO users (id, username, email, password_hash, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
                (user_id, username, email, pw_hash, now, now),
            )

            # Assign admin role
            cursor.execute("SELECT id FROM roles WHERE name = 'admin'")
            admin_role = cursor.fetchone()
            if admin_role:
                cursor.execute(
                    """
                    INSERT INTO user_roles (user_id, role_id, assigned_at)
                    VALUES (?, ?, ?)
                """,
                    (user_id, admin_role["id"], now),
                )

            conn.commit()
            logger.info("Bootstrap administrator account initialized successfully.")

    def authenticate_user(
        self,
        username: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[UserRead, str]:
        """Authenticate username and password, returning UserRead and a secure session ID."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            user_row = cursor.fetchone()

            # Constant-time mitigation against timing enumeration
            if not user_row:
                # Dummy verification to balance execution time
                hasher.verify("$argon2id$v=19$m=65536,t=3,p=4$dummy$dummy", "dummy")
                logger.warning(
                    f"Failed login attempt for non-existent user '{username}' from IP {ip_address}"
                )
                raise UnauthorizedError("Invalid username or password")

            if not user_row["is_active"]:
                logger.warning(f"Login rejected for deactivated user '{username}'")
                raise UnauthorizedError("User account is deactivated")

            if not hasher.verify(user_row["password_hash"], password):
                logger.warning(f"Failed login attempt for user '{username}' from IP {ip_address}")
                raise UnauthorizedError("Invalid username or password")

            user_id = user_row["id"]
            now_dt = datetime.now(timezone.utc)
            now_str = now_dt.isoformat()
            expires_dt = now_dt + timedelta(minutes=settings.TOKEN_EXPIRE_MINUTES)
            expires_str = expires_dt.isoformat()

            # Update last login
            cursor.execute(
                "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
                (now_str, now_str, user_id),
            )

            # Create session
            session_id = f"ses_{secrets.token_hex(32)}"
            cursor.execute(
                """
                INSERT INTO user_sessions (id, user_id, ip_address, user_agent, created_at, expires_at, last_activity_at, is_revoked)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
                (session_id, user_id, ip_address, user_agent, now_str, expires_str, now_str),
            )

            conn.commit()

        user_read = self.get_user_by_id(user_id)
        logger.info(f"User '{username}' logged in successfully from IP {ip_address}")
        return user_read, session_id

    def get_session_user(self, session_id: str) -> Optional[UserRead]:
        """Validate session token and retrieve corresponding active user."""
        if not session_id:
            return None

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT s.id, s.user_id, s.expires_at, s.is_revoked, u.is_active
                FROM user_sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.id = ?
            """,
                (session_id,),
            )
            row = cursor.fetchone()

            if not row or row["is_revoked"] or not row["is_active"]:
                return None

            # Check expiration
            expires_at = datetime.fromisoformat(row["expires_at"])
            now_dt = datetime.now(timezone.utc)
            if expires_at < now_dt:
                # Session expired
                cursor.execute(
                    "UPDATE user_sessions SET is_revoked = 1 WHERE id = ?", (session_id,)
                )
                conn.commit()
                return None

            # Update activity
            cursor.execute(
                "UPDATE user_sessions SET last_activity_at = ? WHERE id = ?",
                (now_dt.isoformat(), session_id),
            )
            conn.commit()

            user_id = row["user_id"]

        return self.get_user_by_id(user_id)

    def revoke_session(self, session_id: str) -> None:
        """Revoke a session."""
        if not session_id:
            return
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE user_sessions SET is_revoked = 1 WHERE id = ?", (session_id,))
            conn.commit()

    def get_user_roles(self, user_id: str) -> List[str]:
        """Retrieve assigned role names for a user."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT r.name FROM roles r
                JOIN user_roles ur ON r.id = ur.role_id
                WHERE ur.user_id = ?
                ORDER BY r.name ASC
            """,
                (user_id,),
            )
            return [row["name"] for row in cursor.fetchall()]

    def get_user_permissions(self, user_id: str) -> List[str]:
        """Retrieve distinct effective permission names granted to a user."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT p.name FROM permissions p
                JOIN role_permissions rp ON p.id = rp.permission_id
                JOIN user_roles ur ON rp.role_id = ur.role_id
                WHERE ur.user_id = ?
                ORDER BY p.name ASC
            """,
                (user_id,),
            )
            return [row["name"] for row in cursor.fetchall()]

    def list_users(self) -> List[UserRead]:
        """List all users with their roles and permissions."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, email, is_active, created_at, updated_at, last_login_at FROM users ORDER BY username ASC"
            )
            users = cursor.fetchall()

        results = []
        for u in users:
            roles = self.get_user_roles(u["id"])
            perms = self.get_user_permissions(u["id"])
            results.append(
                UserRead(
                    id=u["id"],
                    username=u["username"],
                    email=u["email"],
                    is_active=bool(u["is_active"]),
                    created_at=u["created_at"],
                    updated_at=u["updated_at"],
                    last_login_at=u["last_login_at"],
                    roles=roles,
                    permissions=perms,
                )
            )
        return results

    def get_user_by_id(self, user_id: str) -> UserRead:
        """Fetch a specific user by ID."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, email, is_active, created_at, updated_at, last_login_at FROM users WHERE id = ?",
                (user_id,),
            )
            u = cursor.fetchone()
            if not u:
                raise NotFoundError(f"User with ID '{user_id}' not found")

        roles = self.get_user_roles(user_id)
        perms = self.get_user_permissions(user_id)
        return UserRead(
            id=u["id"],
            username=u["username"],
            email=u["email"],
            is_active=bool(u["is_active"]),
            created_at=u["created_at"],
            updated_at=u["updated_at"],
            last_login_at=u["last_login_at"],
            roles=roles,
            permissions=perms,
        )

    def create_user(self, payload: UserCreate) -> UserRead:
        """Create a new user account with assigned roles."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Check unique username
            cursor.execute("SELECT id FROM users WHERE username = ?", (payload.username,))
            if cursor.fetchone():
                raise ConflictError(f"Username '{payload.username}' is already taken")

            # Check unique email
            if payload.email:
                cursor.execute("SELECT id FROM users WHERE email = ?", (str(payload.email),))
                if cursor.fetchone():
                    raise ConflictError(f"Email '{payload.email}' is already registered")

            user_id = f"usr_{uuid.uuid4().hex[:12]}"
            pw_hash = hasher.hash(payload.password)
            now = self._now()

            cursor.execute(
                """
                INSERT INTO users (id, username, email, password_hash, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    user_id,
                    payload.username,
                    str(payload.email) if payload.email else None,
                    pw_hash,
                    1 if payload.is_active else 0,
                    now,
                    now,
                ),
            )

            # Assign roles
            roles_to_assign = payload.roles if payload.roles else ["viewer"]
            for role_name in roles_to_assign:
                cursor.execute("SELECT id FROM roles WHERE name = ?", (role_name,))
                role_row = cursor.fetchone()
                if not role_row:
                    raise NotFoundError(f"Role '{role_name}' does not exist")
                cursor.execute(
                    """
                    INSERT INTO user_roles (user_id, role_id, assigned_at)
                    VALUES (?, ?, ?)
                """,
                    (user_id, role_row["id"], now),
                )

            conn.commit()

        logger.info(f"User '{payload.username}' ({user_id}) created with roles {roles_to_assign}")
        return self.get_user_by_id(user_id)

    def update_user(self, user_id: str, payload: UserUpdate) -> UserRead:
        """Update an existing user account."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, email, is_active FROM users WHERE id = ?", (user_id,)
            )
            user_row = cursor.fetchone()
            if not user_row:
                raise NotFoundError(f"User '{user_id}' not found")

            now = self._now()

            # Email update
            if payload.email is not None:
                email_str = str(payload.email)
                cursor.execute(
                    "SELECT id FROM users WHERE email = ? AND id != ?", (email_str, user_id)
                )
                if cursor.fetchone():
                    raise ConflictError(f"Email '{email_str}' is already taken")
                cursor.execute(
                    "UPDATE users SET email = ?, updated_at = ? WHERE id = ?",
                    (email_str, now, user_id),
                )

            # Password update
            if payload.password is not None:
                pw_hash = hasher.hash(payload.password)
                cursor.execute(
                    "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                    (pw_hash, now, user_id),
                )

            # Active status update
            if payload.is_active is not None:
                cursor.execute(
                    "UPDATE users SET is_active = ?, updated_at = ? WHERE id = ?",
                    (1 if payload.is_active else 0, now, user_id),
                )
                # If deactivating, revoke all sessions
                if not payload.is_active:
                    cursor.execute(
                        "UPDATE user_sessions SET is_revoked = 1 WHERE user_id = ?", (user_id,)
                    )

            # Role updates
            if payload.roles is not None:
                cursor.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
                for role_name in payload.roles:
                    cursor.execute("SELECT id FROM roles WHERE name = ?", (role_name,))
                    role_row = cursor.fetchone()
                    if not role_row:
                        raise NotFoundError(f"Role '{role_name}' does not exist")
                    cursor.execute(
                        """
                        INSERT INTO user_roles (user_id, role_id, assigned_at)
                        VALUES (?, ?, ?)
                    """,
                        (user_id, role_row["id"], now),
                    )

            conn.commit()

        logger.info(f"User '{user_id}' updated successfully")
        return self.get_user_by_id(user_id)

    def delete_user(self, user_id: str, requesting_user_id: str) -> None:
        """Delete a user account."""
        if user_id == requesting_user_id:
            raise BadRequestError("You cannot delete your own active user account")

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
            user_row = cursor.fetchone()
            if not user_row:
                raise NotFoundError(f"User '{user_id}' not found")

            # Check if this user is the only active admin
            cursor.execute(
                """
                SELECT COUNT(DISTINCT u.id) as admin_count
                FROM users u
                JOIN user_roles ur ON u.id = ur.user_id
                JOIN roles r ON ur.role_id = r.id
                WHERE r.name = 'admin' AND u.is_active = 1 AND u.id != ?
            """,
                (user_id,),
            )
            remaining_admins = cursor.fetchone()["admin_count"]
            if remaining_admins == 0:
                # Check if the target user is an admin
                cursor.execute(
                    """
                    SELECT 1 FROM user_roles ur
                    JOIN roles r ON ur.role_id = r.id
                    WHERE ur.user_id = ? AND r.name = 'admin'
                """,
                    (user_id,),
                )
                if cursor.fetchone():
                    raise BadRequestError("Cannot delete the only active administrator account")

            # Cascade delete (sessions, user_roles handled by FK)
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()

        logger.info(f"User '{user_id}' deleted by '{requesting_user_id}'")

    def list_roles(self) -> List[RoleRead]:
        """List all defined roles and their permissions."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, description, is_system, created_at, updated_at FROM roles ORDER BY name ASC"
            )
            roles = cursor.fetchall()

        results = []
        for r in roles:
            role_id = r["id"]
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT p.name FROM permissions p
                    JOIN role_permissions rp ON p.id = rp.permission_id
                    WHERE rp.role_id = ?
                    ORDER BY p.name ASC
                """,
                    (role_id,),
                )
                perms = [p["name"] for p in cursor.fetchall()]

            results.append(
                RoleRead(
                    id=r["id"],
                    name=r["name"],
                    description=r["description"],
                    is_system=bool(r["is_system"]),
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    permissions=perms,
                )
            )
        return results

    def get_role_by_id(self, role_id: str) -> RoleRead:
        """Fetch role by ID."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, description, is_system, created_at, updated_at FROM roles WHERE id = ?",
                (role_id,),
            )
            r = cursor.fetchone()
            if not r:
                raise NotFoundError(f"Role '{role_id}' not found")

            cursor.execute(
                """
                SELECT p.name FROM permissions p
                JOIN role_permissions rp ON p.id = rp.permission_id
                WHERE rp.role_id = ?
                ORDER BY p.name ASC
            """,
                (role_id,),
            )
            perms = [p["name"] for p in cursor.fetchall()]

        return RoleRead(
            id=r["id"],
            name=r["name"],
            description=r["description"],
            is_system=bool(r["is_system"]),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            permissions=perms,
        )

    def create_role(self, payload: RoleCreate) -> RoleRead:
        """Create a custom role with permissions."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM roles WHERE name = ?", (payload.name,))
            if cursor.fetchone():
                raise ConflictError(f"Role '{payload.name}' already exists")

            role_id = f"role_{uuid.uuid4().hex[:10]}"
            now = self._now()

            cursor.execute(
                """
                INSERT INTO roles (id, name, description, is_system, created_at, updated_at)
                VALUES (?, ?, ?, 0, ?, ?)
            """,
                (role_id, payload.name, payload.description, now, now),
            )

            # Link permissions
            for perm_name in payload.permissions:
                cursor.execute("SELECT id FROM permissions WHERE name = ?", (perm_name,))
                p_row = cursor.fetchone()
                if not p_row:
                    raise NotFoundError(f"Permission '{perm_name}' does not exist")
                cursor.execute(
                    """
                    INSERT INTO role_permissions (role_id, permission_id, assigned_at)
                    VALUES (?, ?, ?)
                """,
                    (role_id, p_row["id"], now),
                )

            conn.commit()

        logger.info(
            f"Role '{payload.name}' ({role_id}) created with permissions {payload.permissions}"
        )
        return self.get_role_by_id(role_id)

    def update_role(self, role_id: str, payload: RoleUpdate) -> RoleRead:
        """Update role metadata or granted permissions."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, is_system FROM roles WHERE id = ?", (role_id,))
            role_row = cursor.fetchone()
            if not role_row:
                raise NotFoundError(f"Role '{role_id}' not found")

            now = self._now()

            if payload.name is not None and payload.name != role_row["name"]:
                if role_row["is_system"]:
                    raise BadRequestError("Cannot rename built-in system roles")
                cursor.execute(
                    "SELECT id FROM roles WHERE name = ? AND id != ?", (payload.name, role_id)
                )
                if cursor.fetchone():
                    raise ConflictError(f"Role name '{payload.name}' is already taken")
                cursor.execute(
                    "UPDATE roles SET name = ?, updated_at = ? WHERE id = ?",
                    (payload.name, now, role_id),
                )

            if payload.description is not None:
                cursor.execute(
                    "UPDATE roles SET description = ?, updated_at = ? WHERE id = ?",
                    (payload.description, now, role_id),
                )

            if payload.permissions is not None:
                cursor.execute("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
                for perm_name in payload.permissions:
                    cursor.execute("SELECT id FROM permissions WHERE name = ?", (perm_name,))
                    p_row = cursor.fetchone()
                    if not p_row:
                        raise NotFoundError(f"Permission '{perm_name}' does not exist")
                    cursor.execute(
                        """
                        INSERT INTO role_permissions (role_id, permission_id, assigned_at)
                        VALUES (?, ?, ?)
                    """,
                        (role_id, p_row["id"], now),
                    )

            conn.commit()

        logger.info(f"Role '{role_id}' updated successfully")
        return self.get_role_by_id(role_id)

    def delete_role(self, role_id: str) -> None:
        """Delete a custom role."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, is_system FROM roles WHERE id = ?", (role_id,))
            role_row = cursor.fetchone()
            if not role_row:
                raise NotFoundError(f"Role '{role_id}' not found")

            if role_row["is_system"]:
                raise BadRequestError("Cannot delete built-in system roles")

            cursor.execute("DELETE FROM roles WHERE id = ?", (role_id,))
            conn.commit()

        logger.info(f"Role '{role_id}' deleted")

    def list_permissions(self) -> List[Dict[str, Any]]:
        """List all system permissions."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, description, resource, action, created_at FROM permissions ORDER BY name ASC"
            )
            return [dict(row) for row in cursor.fetchall()]


# Singleton service
auth_service = AuthService()
