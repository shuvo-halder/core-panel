import asyncio
import os
import re
import shutil
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.core.logging import logger

UFW_BINARY_LOCATIONS = (
    "/usr/sbin/ufw",
    "/usr/bin/ufw",
    "/sbin/ufw",
    "/bin/ufw",
)

# Port range or single port
PORT_PATTERN = re.compile(r"^\d+(:\d+)?$")
# Safe comment pattern: alphanumeric, spaces, hyphens, underscores, dots
COMMENT_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.\s]{0,64}$")
# Numbered rule line pattern from `ufw status numbered`
# Example: [ 1] 22/tcp                     ALLOW IN    Anywhere                  # SSH
RULE_LINE_PATTERN = re.compile(
    r"^\s*\[\s*(\d+)\]\s+(.*?)\s{2,}(ALLOW|DENY|REJECT)\s+(IN|OUT)\s{2,}(.*?)(?:\s+#\s*(.*))?$",
    re.IGNORECASE,
)


def resolve_ufw_binary() -> Optional[str]:
    """Resolves and verifies ufw binary location from fixed allowlist."""
    which_bin = shutil.which("ufw")
    if which_bin and which_bin in UFW_BINARY_LOCATIONS and os.access(which_bin, os.X_OK):
        return which_bin

    for candidate in UFW_BINARY_LOCATIONS:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    return None


def _detect_protected_ports() -> Set[int]:
    """
    Independently inspects the system to discover active/configured management ports (SSH and Panel).
    Always includes default SSH port 22.
    Checks sshd_config and active listening sockets in /proc/net/tcp.
    """
    protected: Set[int] = {22}

    # 1. Inspect sshd configuration files
    ssh_config_paths = ["/etc/ssh/sshd_config"]
    config_d = "/etc/ssh/sshd_config.d"
    if os.path.isdir(config_d):
        try:
            for entry in os.listdir(config_d):
                if entry.endswith(".conf"):
                    ssh_config_paths.append(os.path.join(config_d, entry))
        except OSError:
            pass

    for path in ssh_config_paths:
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
                                port_num = int(parts[1])
                                if 1 <= port_num <= 65535:
                                    protected.add(port_num)
                            except ValueError:
                                pass
            except OSError:
                pass

    # 2. Inspect /proc/net/tcp and /proc/net/tcp6 for listening sockets
    for proc_path in ("/proc/net/tcp", "/proc/net/tcp6"):
        if os.path.isfile(proc_path):
            try:
                with open(proc_path, "r", encoding="utf-8", errors="replace") as f:
                    for i, line in enumerate(f):
                        if i == 0:
                            continue
                        tokens = line.strip().split()
                        if len(tokens) >= 4:
                            state = tokens[3]
                            if state == "0A":  # TCP_LISTEN
                                local_addr = tokens[1]
                                if ":" in local_addr:
                                    _, port_hex = local_addr.split(":", 1)
                                    try:
                                        port_dec = int(port_hex, 16)
                                        # Protect port 22 or typical management ports if actively listening
                                        if port_dec == 22:
                                            protected.add(22)
                                    except ValueError:
                                        pass
            except OSError:
                pass

    return protected


def _parse_rule_target(to_str: str) -> Tuple[str, str, str]:
    """
    Parses 'To' column from UFW output into (port, protocol, family).
    Examples:
      '22/tcp' -> ('22', 'tcp', 'ipv4')
      '22/tcp (v6)' -> ('22', 'tcp', 'ipv6')
      '80' -> ('80', 'any', 'ipv4')
      '3000:3010/udp' -> ('3000:3010', 'udp', 'ipv4')
    """
    is_v6 = "(v6)" in to_str
    clean = to_str.replace("(v6)", "").strip()

    if "/" in clean:
        port_part, proto_part = clean.split("/", 1)
        protocol = proto_part.strip().lower()
        port = port_part.strip()
    else:
        port = clean
        protocol = "any"

    family = "ipv6" if is_v6 else "ipv4"
    return port, protocol, family


def _generate_rule_signature(
    action: str,
    direction: str,
    protocol: str,
    port: str,
    source: str,
    family: str,
) -> str:
    """Generates a canonical signature string for deterministic rule identity."""
    clean_src = source.replace("(v6)", "").strip()
    return f"{port.lower()}/{protocol.lower()} {action.upper()} {direction.upper()} {clean_src.lower()} {family.lower()}"


def _parse_ufw_output(verbose_out: str, numbered_out: str) -> Dict[str, Any]:
    """
    Normalizes UFW verbose status and numbered rules output into structured dictionaries.
    Handles active, inactive, default policies, and numbered rules with comments.
    """
    is_active = "Status: active" in verbose_out or "Status: active" in numbered_out

    default_incoming = "deny"
    default_outgoing = "allow"
    default_routed = "disabled"

    # Extract default policies from verbose output
    # Example: Default: deny (incoming), allow (outgoing), disabled (routed)
    policy_match = re.search(
        r"Default:\s+(\w+)\s+\(incoming\),\s+(\w+)\s+\(outgoing\)(?:,\s+(\w+)\s+\(routed\))?",
        verbose_out,
        re.IGNORECASE,
    )
    if policy_match:
        default_incoming = policy_match.group(1).lower()
        default_outgoing = policy_match.group(2).lower()
        if policy_match.group(3):
            default_routed = policy_match.group(3).lower()

    rules: List[Dict[str, Any]] = []

    if is_active and numbered_out:
        for line in numbered_out.splitlines():
            line_str = line.strip()
            match = RULE_LINE_PATTERN.match(line_str)
            if not match:
                continue

            index_str, to_part, action, direction, from_part, comment = match.groups()
            rule_index = int(index_str)

            port, protocol, family = _parse_rule_target(to_part)
            source = from_part.strip()
            if "(v6)" in source:
                family = "ipv6"

            rule_action = action.upper()
            rule_direction = direction.upper()
            rule_comment = comment.strip() if comment else None

            sig = _generate_rule_signature(
                action=rule_action,
                direction=rule_direction,
                protocol=protocol,
                port=port,
                source=source,
                family=family,
            )

            rules.append({
                "rule_index": rule_index,
                "port": port,
                "protocol": protocol,
                "action": rule_action,
                "direction": rule_direction,
                "source": source,
                "family": family,
                "comment": rule_comment,
                "signature": sig,
            })

    return {
        "installed": True,
        "active": is_active,
        "default_incoming": default_incoming,
        "default_outgoing": default_outgoing,
        "default_routed": default_routed,
        "rules": rules,
    }


def _is_port_covered(rule: Dict[str, Any], target_port: int) -> bool:
    """Checks if a rule covers a specific numerical port."""
    port_str = rule.get("port", "")
    if ":" in port_str:
        try:
            p_start, p_end = port_str.split(":", 1)
            return int(p_start) <= target_port <= int(p_end)
        except ValueError:
            return False
    else:
        try:
            return int(port_str) == target_port
        except ValueError:
            return False


async def handle_firewall_status(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Operation: firewall.status
    Returns normalized status and parsed numbered rules from UFW.
    """
    ufw_bin = resolve_ufw_binary()
    if not ufw_bin:
        return {
            "success": True,
            "installed": False,
            "active": False,
            "default_incoming": "deny",
            "default_outgoing": "allow",
            "default_routed": "disabled",
            "rules": [],
            "management_ports": sorted(list(_detect_protected_ports())),
        }

    try:
        # Run ufw status verbose
        proc_verbose = await asyncio.create_subprocess_exec(
            ufw_bin,
            "status",
            "verbose",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_v, stderr_v = await asyncio.wait_for(proc_verbose.communicate(), timeout=10.0)

        # Run ufw status numbered
        proc_numbered = await asyncio.create_subprocess_exec(
            ufw_bin,
            "status",
            "numbered",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_n, stderr_n = await asyncio.wait_for(proc_numbered.communicate(), timeout=10.0)

        verbose_out = stdout_v.decode("utf-8", errors="replace")
        numbered_out = stdout_n.decode("utf-8", errors="replace")

        parsed = _parse_ufw_output(verbose_out, numbered_out)
        parsed["management_ports"] = sorted(list(_detect_protected_ports()))
        parsed["success"] = True
        return parsed

    except asyncio.TimeoutError:
        logger.error("CoreAgent timeout while querying UFW status")
        return {"success": False, "error": "Timeout querying firewall status"}
    except Exception as exc:
        logger.error(f"CoreAgent error querying UFW status: {exc}")
        return {"success": False, "error": f"Failed to query firewall status: {exc}"}


async def handle_firewall_rule_add(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Operation: firewall.rule_add
    Adds a validated allow or deny rule using fixed argv syntax.
    Enforces independent lockout protection in CoreAgent.
    """
    ufw_bin = resolve_ufw_binary()
    if not ufw_bin:
        return {"success": False, "error": "UFW firewall is not installed on this system"}

    port = str(payload.get("port", "")).strip()
    protocol = str(payload.get("protocol", "any")).strip().lower()
    action = str(payload.get("action", "allow")).strip().lower()
    direction = str(payload.get("direction", "in")).strip().lower()
    source_ip = str(payload.get("source_ip", "any")).strip()
    comment = str(payload.get("comment", "")).strip() if payload.get("comment") else None

    # 1. Independent CoreAgent validation
    if not PORT_PATTERN.match(port):
        return {"success": False, "error": f"Invalid port or port range: '{port}'"}

    if protocol not in ("tcp", "udp", "any"):
        return {"success": False, "error": f"Invalid protocol: '{protocol}'. Allowed: tcp, udp, any"}

    if action not in ("allow", "deny"):
        return {"success": False, "error": f"Invalid action: '{action}'. Allowed: allow, deny"}

    if direction not in ("in", "out"):
        return {"success": False, "error": f"Invalid direction: '{direction}'. Allowed: in, out"}

    if comment:
        if not COMMENT_PATTERN.match(comment):
            return {"success": False, "error": "Invalid comment: prohibited characters or exceeds 64 chars"}

    # 2. Independent Lockout Protection
    protected_ports = _detect_protected_ports()
    if action == "deny" and direction == "in":
        # Check if the deny rule targets any protected management port
        is_protected_target = False
        if ":" in port:
            try:
                p_start, p_end = port.split(":", 1)
                for pp in protected_ports:
                    if int(p_start) <= pp <= int(p_end):
                        is_protected_target = True
                        break
            except ValueError:
                pass
        else:
            try:
                if int(port) in protected_ports:
                    is_protected_target = True
            except ValueError:
                pass

        if is_protected_target and (source_ip.lower() in ("any", "anywhere", "0.0.0.0/0", "::/0")):
            return {
                "success": False,
                "error": f"Lockout hazard: Cannot add DENY rule targeting active management port ({port}).",
                "lockout_risk": True,
            }

    # 3. Construct fixed argv arguments
    # Syntax: ufw [allow|deny] [in|out] [proto <tcp|udp>] [from <source>] [to any port <port>] [comment <comment>]
    cmd_args = [ufw_bin, action, direction]

    if protocol in ("tcp", "udp"):
        cmd_args.extend(["proto", protocol])

    if source_ip and source_ip.lower() not in ("any", "anywhere"):
        cmd_args.extend(["from", source_ip])
    else:
        cmd_args.extend(["from", "any"])

    cmd_args.extend(["to", "any", "port", port])

    if comment:
        cmd_args.extend(["comment", comment])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15.0)
        out_str = stdout.decode("utf-8", errors="replace")
        err_str = stderr.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            logger.error(f"UFW rule add failed (code {proc.returncode}): {err_str or out_str}")
            return {"success": False, "error": f"Failed to add rule: {err_str or out_str}"}

        logger.info(f"Firewall rule added successfully: {action} {direction} {port}/{protocol}")
        return {"success": True, "message": f"Rule added: {action} {direction} {port}/{protocol}"}

    except asyncio.TimeoutError:
        logger.error("CoreAgent timeout while executing ufw rule add")
        return {"success": False, "error": "Timeout executing firewall command"}
    except Exception as exc:
        logger.error(f"CoreAgent error executing ufw rule add: {exc}")
        return {"success": False, "error": f"Subprocess error: {exc}"}


async def handle_firewall_rule_delete(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Operation: firewall.rule_delete
    Deletes an existing rule by index with strict signature concurrency verification
    and independent lockout protection.
    """
    ufw_bin = resolve_ufw_binary()
    if not ufw_bin:
        return {"success": False, "error": "UFW firewall is not installed on this system"}

    try:
        rule_index = int(payload.get("rule_index", 0))
    except (TypeError, ValueError):
        return {"success": False, "error": "Invalid rule index: must be a positive integer"}

    if rule_index < 1:
        return {"success": False, "error": "Invalid rule index: must be >= 1"}

    expected_signature = payload.get("expected_rule_signature")

    # 1. Fetch current firewall state
    current_status = await handle_firewall_status({})
    if not current_status.get("success"):
        return {"success": False, "error": "Cannot verify firewall rules before deletion"}

    rules = current_status.get("rules", [])
    target_rule = next((r for r in rules if r.get("rule_index") == rule_index), None)
    if not target_rule:
        return {
            "success": False,
            "error": f"Rule #{rule_index} not found. The rule list may have changed.",
            "not_found": True,
        }

    # 2. Concurrency check: Verify signature
    if expected_signature:
        actual_sig = target_rule.get("signature", "")
        if actual_sig.lower() != expected_signature.strip().lower():
            logger.warning(
                f"Rule index concurrency conflict: expected '{expected_signature}', found '{actual_sig}'"
            )
            return {
                "success": False,
                "error": f"Rule list modified by another process. Target rule signature mismatch.",
                "conflict": True,
                "current_signature": actual_sig,
            }

    # 3. Lockout Protection Check on Deletion
    # If target rule is ALLOW IN covering a protected management port, verify another rule covers it
    protected_ports = _detect_protected_ports()
    default_incoming = current_status.get("default_incoming", "deny")

    if target_rule.get("action") == "ALLOW" and target_rule.get("direction") == "IN":
        for p in protected_ports:
            if _is_port_covered(target_rule, p):
                # Count how many other active ALLOW IN rules cover this port
                other_allow_count = sum(
                    1
                    for r in rules
                    if r.get("rule_index") != rule_index
                    and r.get("action") == "ALLOW"
                    and r.get("direction") == "IN"
                    and _is_port_covered(r, p)
                )
                if other_allow_count == 0 and default_incoming in ("deny", "reject"):
                    return {
                        "success": False,
                        "error": f"Lockout hazard: Cannot delete rule #{rule_index}. It is the only rule permitting incoming SSH access on port {p}.",
                        "lockout_risk": True,
                    }

    # 4. Execute deletion with --force to bypass interactive prompt
    # Syntax: ufw --force delete <rule_index>
    try:
        proc = await asyncio.create_subprocess_exec(
            ufw_bin,
            "--force",
            "delete",
            str(rule_index),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15.0)
        out_str = stdout.decode("utf-8", errors="replace")
        err_str = stderr.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            logger.error(f"UFW rule delete failed (code {proc.returncode}): {err_str or out_str}")
            return {"success": False, "error": f"Failed to delete rule: {err_str or out_str}"}

        logger.info(f"Firewall rule #{rule_index} deleted successfully")
        return {"success": True, "message": f"Rule #{rule_index} deleted successfully"}

    except asyncio.TimeoutError:
        logger.error("CoreAgent timeout while executing ufw rule delete")
        return {"success": False, "error": "Timeout executing firewall command"}
    except Exception as exc:
        logger.error(f"CoreAgent error executing ufw rule delete: {exc}")
        return {"success": False, "error": f"Subprocess error: {exc}"}


async def handle_firewall_toggle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Operation: firewall.toggle
    Safely enables or disables UFW.
    When enabling, enforces that at least one active rule permits incoming management traffic.
    """
    ufw_bin = resolve_ufw_binary()
    if not ufw_bin:
        return {"success": False, "error": "UFW firewall is not installed on this system"}

    enable = bool(payload.get("enable", False))

    if enable:
        # Pre-enable Lockout Verification:
        # Verify that an active rule permits SSH/management traffic if incoming policy is deny
        current_status = await handle_firewall_status({})
        rules = current_status.get("rules", [])
        protected_ports = _detect_protected_ports()
        default_incoming = current_status.get("default_incoming", "deny")

        if default_incoming in ("deny", "reject"):
            ssh_allowed = any(
                r.get("action") == "ALLOW"
                and r.get("direction") == "IN"
                and any(_is_port_covered(r, p) for p in protected_ports)
                for r in rules
            )
            if not ssh_allowed:
                return {
                    "success": False,
                    "error": (
                        f"Lockout hazard: Cannot enable firewall. No active rule permits incoming SSH "
                        f"traffic on management port(s) {sorted(list(protected_ports))}. "
                        "Add an allow rule for SSH before enabling."
                    ),
                    "lockout_risk": True,
                }

        cmd_args = [ufw_bin, "--force", "enable"]
    else:
        cmd_args = [ufw_bin, "disable"]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15.0)
        out_str = stdout.decode("utf-8", errors="replace")
        err_str = stderr.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            logger.error(f"UFW toggle failed (code {proc.returncode}): {err_str or out_str}")
            return {"success": False, "error": f"Failed to change firewall state: {err_str or out_str}"}

        state_str = "enabled" if enable else "disabled"
        logger.info(f"Firewall {state_str} successfully")
        return {"success": True, "active": enable, "message": f"Firewall {state_str} successfully"}

    except asyncio.TimeoutError:
        logger.error("CoreAgent timeout while toggling firewall")
        return {"success": False, "error": "Timeout executing firewall toggle"}
    except Exception as exc:
        logger.error(f"CoreAgent error toggling firewall: {exc}")
        return {"success": False, "error": f"Subprocess error: {exc}"}
