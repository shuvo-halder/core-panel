import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set

from backend.app.core.config import settings
from backend.app.core.errors import (
    AppError,
    BadRequestError,
    ConflictError,
    NotFoundError,
)
from backend.app.core.validators import (
    validate_firewall_action,
    validate_firewall_comment,
    validate_firewall_direction,
    validate_firewall_port,
    validate_firewall_protocol,
    validate_firewall_source,
)
from backend.app.ipc.client import (
    AgentExecutionError,
    AgentUnavailableError,
    IPCClient,
)
from backend.app.linux.contracts import (
    FirewallRule,
    FirewallRuleCreate,
    FirewallStatus,
    IFirewallManager,
)

logger = logging.getLogger("corepanel.linux.firewall")


class IFirewallProvider(ABC):
    """Abstract contract for specific Linux packet filtering backends (e.g. UFW)."""

    @abstractmethod
    async def get_status(self) -> FirewallStatus:
        pass

    @abstractmethod
    async def add_rule(self, rule: FirewallRuleCreate) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def delete_rule(
        self, rule_index: int, expected_signature: Optional[str] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def toggle(self, enable: bool) -> Dict[str, Any]:
        pass


class UFWFirewallProvider(IFirewallProvider):
    """
    UFW (Uncomplicated Firewall) provider implementation.
    Delegates all privileged firewall queries and mutations exclusively
    to CoreAgent via Unix Domain Socket IPC with fail-closed semantics.
    FastAPI never executes ufw commands directly.
    """

    def __init__(
        self,
        socket_path: str = "/run/corepanel/agent.sock",
        ipc_client: Optional[IPCClient] = None,
    ):
        self.socket_path = socket_path
        self.ipc_client = ipc_client or IPCClient(socket_path=socket_path)

    async def _call_agent(self, op_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invokes CoreAgent operations over Unix Domain Socket IPC.
        Fail-closed: if socket is unreachable or times out, immediately raises
        AppError(code="IPC_UNAVAILABLE", status_code=503).
        """
        try:
            return await self.ipc_client.execute(op_name, payload)
        except AgentUnavailableError as e:
            logger.error(f"CoreAgent IPC unavailable for {op_name}: {e}")
            raise AppError(
                message="Privileged CoreAgent service is unreachable. Firewall operation aborted.",
                code="IPC_UNAVAILABLE",
                status_code=503,
            )
        except AgentExecutionError as e:
            logger.error(f"CoreAgent execution error for {op_name}: {e}")
            raise AppError(
                message=f"Agent firewall operation failed: {e.message}",
                code="AGENT_EXECUTION_ERROR",
                status_code=500,
                details=e.details,
            )

    async def get_status(self) -> FirewallStatus:
        res = await self._call_agent("firewall.status", {})
        if not res.get("success", False):
            raise AppError(
                message=res.get("error", "Failed to retrieve firewall status"),
                code="FIREWALL_STATUS_FAILED",
                status_code=500,
            )

        rules: List[FirewallRule] = []
        for r in res.get("rules", []):
            rules.append(
                FirewallRule(
                    rule_index=r.get("rule_index", 0),
                    port=str(r.get("port", "")),
                    protocol=str(r.get("protocol", "any")),
                    action=str(r.get("action", "")),
                    direction=str(r.get("direction", "IN")),
                    source=str(r.get("source", "Anywhere")),
                    family=str(r.get("family", "ipv4")),
                    comment=r.get("comment"),
                    signature=r.get("signature"),
                )
            )

        return FirewallStatus(
            installed=bool(res.get("installed", False)),
            active=bool(res.get("active", False)),
            default_incoming=str(res.get("default_incoming", "deny")),
            default_outgoing=str(res.get("default_outgoing", "allow")),
            default_routed=str(res.get("default_routed", "disabled")),
            rules=rules,
            management_ports=list(res.get("management_ports", [22])),
        )

    async def add_rule(self, rule: FirewallRuleCreate) -> Dict[str, Any]:
        payload = {
            "port": rule.port,
            "protocol": rule.protocol,
            "action": rule.action,
            "direction": rule.direction,
            "source_ip": rule.source_ip,
            "comment": rule.comment,
        }
        return await self._call_agent("firewall.rule_add", payload)

    async def delete_rule(
        self, rule_index: int, expected_signature: Optional[str] = None
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"rule_index": rule_index}
        if expected_signature:
            payload["expected_rule_signature"] = expected_signature
        return await self._call_agent("firewall.rule_delete", payload)

    async def toggle(self, enable: bool) -> Dict[str, Any]:
        return await self._call_agent("firewall.toggle", {"enable": enable})


class LinuxFirewallManager(IFirewallManager):
    """
    Linux Firewall Manager implementation.
    Orchestrates firewall provider execution with defense-in-depth:
    - Centralized parameter validation
    - Dual-layer management lockout protection
    - Concurrency check on rule deletion
    - Auditable structured errors
    """

    def __init__(self, provider: Optional[IFirewallProvider] = None):
        self.provider = provider or UFWFirewallProvider()

    def _detect_protected_ports(self) -> Set[int]:
        """
        Discovers active management ports that must not be blocked (SSH and Panel port).
        Always includes port 22.
        """
        protected: Set[int] = {22}
        try:
            if hasattr(settings, "PORT") and 1 <= settings.PORT <= 65535:
                protected.add(settings.PORT)
        except Exception:
            pass

        # Inspect sshd config if readable by unprivileged user
        for path in ("/etc/ssh/sshd_config",):
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        for line in f:
                            clean = line.strip()
                            if clean.startswith("#") or not clean:
                                continue
                            parts = clean.split()
                            if len(parts) >= 2 and parts[0].lower() == "port":
                                try:
                                    p = int(parts[1])
                                    if 1 <= p <= 65535:
                                        protected.add(p)
                                except ValueError:
                                    pass
                except OSError:
                    pass

        return protected

    def _rule_covers_port(self, rule: FirewallRule, target_port: int) -> bool:
        """Checks if a rule covers a specific numerical port."""
        if ":" in rule.port:
            try:
                p_start, p_end = rule.port.split(":", 1)
                return int(p_start) <= target_port <= int(p_end)
            except ValueError:
                return False
        else:
            try:
                return int(rule.port) == target_port
            except ValueError:
                return False

    async def get_status(self) -> FirewallStatus:
        """Retrieves normalized firewall state and rule list from provider."""
        return await self.provider.get_status()

    async def add_rule(self, rule: FirewallRuleCreate) -> Dict[str, Any]:
        """
        Validates and dispatches rule creation.
        Enforces defense-in-depth lockout protection:
        Rejects DENY rules targeting active SSH/management ports.
        """
        # 1. Strict Validation
        valid_port = validate_firewall_port(rule.port)
        valid_proto = validate_firewall_protocol(rule.protocol)
        valid_action = validate_firewall_action(rule.action)
        valid_direction = validate_firewall_direction(rule.direction)
        valid_source = validate_firewall_source(rule.source_ip)
        valid_comment = validate_firewall_comment(rule.comment)

        # 2. Defense-in-Depth Lockout Check
        if valid_action == "deny" and valid_direction == "in":
            protected_ports = self._detect_protected_ports()
            is_protected_target = False
            if ":" in valid_port:
                try:
                    p_start, p_end = valid_port.split(":", 1)
                    for pp in protected_ports:
                        if int(p_start) <= pp <= int(p_end):
                            is_protected_target = True
                            break
                except ValueError:
                    pass
            else:
                try:
                    if int(valid_port) in protected_ports:
                        is_protected_target = True
                except ValueError:
                    pass

            if is_protected_target and valid_source in ("any", "0.0.0.0/0", "::/0"):
                raise BadRequestError(
                    f"Lockout hazard: Cannot add DENY rule targeting protected SSH/management port ({valid_port}). This would cause an immediate server lockout.",
                    code="FIREWALL_LOCKOUT_RISK",
                )

        clean_rule = FirewallRuleCreate(
            port=valid_port,
            protocol=valid_proto,
            action=valid_action,
            direction=valid_direction,
            source_ip=valid_source,
            comment=valid_comment,
        )

        # 3. Dispatch to Provider
        res = await self.provider.add_rule(clean_rule)
        if not res.get("success"):
            if res.get("lockout_risk"):
                raise BadRequestError(res.get("error", "Lockout risk detected"), code="FIREWALL_LOCKOUT_RISK")
            raise BadRequestError(res.get("error", "Failed to add firewall rule"), code="FIREWALL_MUTATION_FAILED")

        return res

    async def delete_rule(
        self, rule_index: int, expected_signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Deletes rule with signature concurrency check and lockout protection.
        """
        if rule_index < 1:
            raise BadRequestError("Rule index must be a positive integer", code="INVALID_RULE_INDEX")

        # 1. Fetch current status to verify rule existence and signature
        current_status = await self.get_status()
        target_rule = next((r for r in current_status.rules if r.rule_index == rule_index), None)
        if not target_rule:
            raise NotFoundError(
                f"Firewall rule #{rule_index} not found. The rule list may have changed.",
                code="FIREWALL_RULE_NOT_FOUND",
            )

        # 2. Concurrency signature comparison
        if expected_signature and target_rule.signature:
            if target_rule.signature.strip().lower() != expected_signature.strip().lower():
                raise ConflictError(
                    "Firewall rule signature mismatch. The rule at this index was modified concurrently.",
                    code="FIREWALL_RULE_CONFLICT",
                )

        # 3. Defense-in-Depth Lockout Check
        protected_ports = self._detect_protected_ports()
        if target_rule.action == "ALLOW" and target_rule.direction == "IN":
            for p in protected_ports:
                if self._rule_covers_port(target_rule, p):
                    # Count other active rules permitting incoming to this port
                    other_allow = sum(
                        1
                        for r in current_status.rules
                        if r.rule_index != rule_index
                        and r.action == "ALLOW"
                        and r.direction == "IN"
                        and self._rule_covers_port(r, p)
                    )
                    if other_allow == 0 and current_status.default_incoming in ("deny", "reject"):
                        raise BadRequestError(
                            f"Lockout hazard: Cannot delete rule #{rule_index}. It is the only active rule permitting incoming SSH traffic on port {p}. Add an alternative allow rule first.",
                            code="FIREWALL_LOCKOUT_RISK",
                        )

        # 4. Dispatch to Provider
        res = await self.provider.delete_rule(
            rule_index=rule_index,
            expected_signature=expected_signature or target_rule.signature,
        )
        if not res.get("success"):
            if res.get("conflict"):
                raise ConflictError(res.get("error", "Rule concurrency conflict"), code="FIREWALL_RULE_CONFLICT")
            if res.get("not_found"):
                raise NotFoundError(res.get("error", "Rule not found"), code="FIREWALL_RULE_NOT_FOUND")
            if res.get("lockout_risk"):
                raise BadRequestError(res.get("error", "Lockout risk detected"), code="FIREWALL_LOCKOUT_RISK")
            raise BadRequestError(res.get("error", "Failed to delete rule"), code="FIREWALL_MUTATION_FAILED")

        return res

    async def toggle_firewall(self, enable: bool) -> Dict[str, Any]:
        """
        Safely toggles firewall state with pre-enable lockout verification.
        """
        if enable:
            current_status = await self.get_status()
            protected_ports = self._detect_protected_ports()
            if current_status.default_incoming in ("deny", "reject"):
                ssh_allowed = any(
                    r.action == "ALLOW"
                    and r.direction == "IN"
                    and any(self._rule_covers_port(r, p) for p in protected_ports)
                    for r in current_status.rules
                )
                if not ssh_allowed:
                    raise BadRequestError(
                        f"Lockout hazard: Cannot enable firewall. No active rule permits incoming SSH traffic on port(s) {sorted(list(protected_ports))}. Add an allow rule for SSH before enabling.",
                        code="FIREWALL_LOCKOUT_RISK",
                    )

        res = await self.provider.toggle(enable)
        if not res.get("success"):
            if res.get("lockout_risk"):
                raise BadRequestError(res.get("error", "Lockout risk detected"), code="FIREWALL_LOCKOUT_RISK")
            raise BadRequestError(res.get("error", "Failed to toggle firewall"), code="FIREWALL_MUTATION_FAILED")

        return res
