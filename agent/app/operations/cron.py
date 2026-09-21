import asyncio
import hashlib
import os
import pwd
import re
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.logging import logger

CRON_USER_PATTERN = re.compile(r"^[a-zA-Z0-9_.][a-zA-Z0-9_.-]*$")
PROHIBITED_CHARS_PATTERN = re.compile(r"[\s/\\;\|\&\>\<\$\`\'\"\x00\n\r\t]")
SPECIAL_CRON_EXPRESSIONS = {
    "@reboot",
    "@hourly",
    "@daily",
    "@midnight",
    "@weekly",
    "@monthly",
    "@yearly",
    "@annually",
}
MONTH_NAMES = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
}
DOW_NAMES = {
    "SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6
}


def _validate_agent_user(username: Any) -> str:
    """Independent validation of user account within CoreAgent boundary."""
    if not isinstance(username, str):
        raise ValueError("Invalid username: must be a string")

    clean = username.strip()
    if not clean or len(clean) > 32:
        raise ValueError(f"Invalid username length: '{clean}'")

    if PROHIBITED_CHARS_PATTERN.search(clean) or ".." in clean or "/" in clean or "\\" in clean:
        raise ValueError("Invalid username: prohibited characters or path separators detected")

    if not CRON_USER_PATTERN.match(clean):
        raise ValueError(f"Invalid username syntax: '{clean}'")

    try:
        pwd.getpwnam(clean)
    except KeyError:
        raise ValueError(f"User account '{clean}' does not exist on host system")

    return clean


def _validate_agent_field(field_val: str, min_val: int, max_val: int, name_map: Optional[dict] = None) -> None:
    if not field_val:
        raise ValueError("Cron field cannot be empty")

    for sub in field_val.split(","):
        sub = sub.strip()
        if not sub:
            raise ValueError("Invalid empty token in cron list field")

        if "/" in sub:
            parts = sub.split("/")
            if len(parts) != 2:
                raise ValueError(f"Invalid step expression: '{sub}'")
            base, step_str = parts[0], parts[1]
            if not step_str.isdigit() or int(step_str) <= 0:
                raise ValueError(f"Step value must be positive integer: '{step_str}'")
            sub = base

        if sub == "*":
            continue

        if "-" in sub:
            parts = sub.split("-")
            if len(parts) != 2:
                raise ValueError(f"Invalid range expression: '{sub}'")
            start_str, end_str = parts[0].upper(), parts[1].upper()
            start_num = name_map.get(start_str) if name_map and start_str in name_map else (int(start_str) if start_str.isdigit() else None)
            end_num = name_map.get(end_str) if name_map and end_str in name_map else (int(end_str) if end_str.isdigit() else None)
            if start_num is None or end_num is None:
                raise ValueError(f"Invalid range bounds: '{sub}'")
            if start_num < min_val or start_num > max_val or end_num < min_val or end_num > max_val:
                raise ValueError(f"Range out of bounds ({min_val}-{max_val}): '{sub}'")
        else:
            val_str = sub.upper()
            val_num = name_map.get(val_str) if name_map and val_str in name_map else (int(val_str) if val_str.isdigit() else None)
            if val_num is None:
                raise ValueError(f"Invalid token: '{sub}'")
            if val_num < min_val or val_num > max_val:
                raise ValueError(f"Value out of bounds ({min_val}-{max_val}): '{sub}'")


def _validate_agent_schedule(schedule: Any) -> str:
    """Independent validation of cron schedule within CoreAgent."""
    if not isinstance(schedule, str):
        raise ValueError("Schedule must be a string")

    clean = schedule.strip()
    if not clean:
        raise ValueError("Schedule cannot be empty")

    if clean.startswith("@"):
        lower = clean.lower()
        if lower not in SPECIAL_CRON_EXPRESSIONS:
            raise ValueError(f"Unsupported special expression: '{clean}'")
        return lower

    fields = clean.split()
    if len(fields) != 5:
        raise ValueError(f"Cron schedule must have exactly 5 fields, got {len(fields)}")

    _validate_agent_field(fields[0], 0, 59)
    _validate_agent_field(fields[1], 0, 23)
    _validate_agent_field(fields[2], 1, 31)
    _validate_agent_field(fields[3], 1, 12, MONTH_NAMES)
    _validate_agent_field(fields[4], 0, 7, DOW_NAMES)

    return " ".join(fields)


def _validate_agent_command(command: Any) -> str:
    """Validates command as data only. Never executed."""
    if not isinstance(command, str):
        raise ValueError("Command must be a string")

    clean = command.strip()
    if not clean:
        raise ValueError("Command cannot be empty")

    if len(clean) > 2048:
        raise ValueError(f"Command exceeds 2048 character limit ({len(clean)})")

    if "\x00" in clean:
        raise ValueError("Command contains illegal null bytes")

    if "\n" in clean or "\r" in clean:
        raise ValueError("Command cannot contain unescaped newline or carriage return characters")

    return clean


def _validate_agent_comment(comment: Any) -> Optional[str]:
    if comment is None:
        return None
    if not isinstance(comment, str):
        raise ValueError("Comment must be a string")
    clean = comment.strip()
    if not clean:
        return None
    if len(clean) > 512:
        raise ValueError(f"Comment exceeds 512 character limit ({len(clean)})")
    if "\x00" in clean or "\n" in clean or "\r" in clean:
        raise ValueError("Comment cannot contain null bytes or newlines")
    return clean


def _resolve_crontab_bin() -> Optional[str]:
    """Finds crontab executable if present on host system."""
    crontab_bin = shutil.which("crontab")
    if not crontab_bin:
        for fallback in ("/usr/bin/crontab", "/bin/crontab"):
            if os.path.isfile(fallback) and os.access(fallback, os.X_OK):
                return fallback
    return crontab_bin


def _get_spool_path(username: str) -> str:
    """Resolves standard spool path for user crontabs."""
    for base in ("/var/spool/cron/crontabs", "/var/spool/cron"):
        p = os.path.join(base, username)
        if os.path.exists(p):
            return p
    # Default to /var/spool/cron/crontabs/<username>
    return os.path.join("/var/spool/cron/crontabs", username)


async def _read_user_crontab_content(username: str) -> str:
    """
    Safely reads current crontab for user.
    Uses 'crontab -u <user> -l' with fixed arguments if available, or direct spool file fallback.
    """
    crontab_bin = _resolve_crontab_bin()
    if crontab_bin:
        proc = await asyncio.create_subprocess_exec(
            crontab_bin,
            "-u",
            username,
            "-l",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError("crontab -l timed out after 5.0 seconds")

        if proc.returncode == 0:
            return stdout.decode("utf-8", errors="replace")

        err_msg = stderr.decode("utf-8", errors="replace").lower()
        if "no crontab for" in err_msg:
            return ""
        raise RuntimeError(f"crontab -l failed with code {proc.returncode}: {stderr.decode('utf-8', errors='replace').strip()}")

    # Fallback to direct spool read if crontab binary is not present
    spool_path = _get_spool_path(username)
    if os.path.isfile(spool_path):
        try:
            with open(spool_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Error reading spool file {spool_path}: {e}")
            return ""

    return ""


async def _write_user_crontab_content(username: str, content: str) -> None:
    """
    Safely writes new crontab content for user.
    Uses secure tempfile and 'crontab -u <user> <file>' with fixed arguments if available,
    or atomic replace on spool file.
    """
    if content and not content.endswith("\n"):
        content += "\n"

    crontab_bin = _resolve_crontab_bin()
    if crontab_bin:
        fd, temp_path = tempfile.mkstemp(prefix=f"cron_{username}_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.chmod(temp_path, 0o600)

            proc = await asyncio.create_subprocess_exec(
                crontab_bin,
                "-u",
                username,
                temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()
                raise RuntimeError("crontab installation timed out after 5.0 seconds")

            if proc.returncode != 0:
                err_text = stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"crontab installation failed with code {proc.returncode}: {err_text}")
        finally:
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
        return

    # Fallback: direct atomic write to spool directory
    spool_dir = "/var/spool/cron/crontabs"
    if not os.path.exists(spool_dir):
        os.makedirs(spool_dir, mode=0o755, exist_ok=True)

    dest_path = os.path.join(spool_dir, username)
    fd, temp_path = tempfile.mkstemp(dir=spool_dir, prefix=f".{username}_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(temp_path, 0o600)
        try:
            pw = pwd.getpwnam(username)
            os.chown(temp_path, pw.pw_uid, pw.pw_gid)
        except Exception:
            pass
        os.replace(temp_path, dest_path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def _compute_job_hash(owner: str, schedule: str, command: str, line_idx: int) -> str:
    """Generates a stable SHA-256 fingerprint for optimistic concurrency verification."""
    data = f"{owner}:{schedule}:{command}:{line_idx}".encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:16]


def _compute_job_id(owner: str, schedule: str, command: str, source: str, source_file: Optional[str], line_idx: int) -> str:
    """Generates a unique, deterministic ID for an identified cron job."""
    raw = f"{source}:{source_file or ''}:{owner}:{schedule}:{command}:{line_idx}".encode("utf-8")
    return f"cron_{hashlib.sha256(raw).hexdigest()[:12]}"


def _parse_crontab_lines(raw_text: str, owner: str, source: str, source_file: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Parses crontab content into structured jobs while identifying comments, disabled jobs, and line indices.
    Preserves comment lines and framing metadata.
    """
    lines = raw_text.splitlines()
    parsed_jobs: List[Dict[str, Any]] = []
    pending_comment: Optional[str] = None

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            pending_comment = None
            continue

        # Check for disabled job: starts with # followed by schedule and command
        # e.g. "# DISABLED: 0 2 * * * /backup" or "# 0 2 * * * /backup"
        is_disabled = False
        potential_job_line = stripped

        if stripped.startswith("#"):
            after_hash = stripped.lstrip("#").strip()
            if after_hash.upper().startswith("DISABLED:"):
                after_hash = after_hash[9:].strip()
                is_disabled = True
            elif after_hash.startswith("@") or (len(after_hash.split()) >= 6 and after_hash.split()[0] in ("*", "*/", "0", "1", "2", "3", "4", "5")):
                # Check if it resembles a commented-out cron schedule
                is_disabled = True

            if is_disabled:
                potential_job_line = after_hash
            else:
                # Normal comment line
                clean_comment = stripped.lstrip("#").strip()
                pending_comment = clean_comment if not pending_comment else f"{pending_comment}; {clean_comment}"
                continue

        # Handle environment variables (e.g. MAILTO=root, PATH=...)
        if "=" in potential_job_line and not potential_job_line.startswith("@") and len(potential_job_line.split()[0].split("=")) == 2:
            pending_comment = None
            continue

        # Parse schedule and command
        schedule = ""
        command = ""
        minute = ""
        hour = ""
        dom = ""
        month = ""
        dow = ""
        special_expr = None

        if potential_job_line.startswith("@"):
            tokens = potential_job_line.split(maxsplit=1)
            if len(tokens) >= 2:
                special_expr = tokens[0].lower()
                schedule = special_expr
                command = tokens[1]
            else:
                continue
        else:
            tokens = potential_job_line.split(maxsplit=5)
            if len(tokens) >= 6:
                minute, hour, dom, month, dow = tokens[0], tokens[1], tokens[2], tokens[3], tokens[4]
                schedule = f"{minute} {hour} {dom} {month} {dow}"
                command = tokens[5]
            else:
                continue

        job_hash = _compute_job_hash(owner, schedule, command, idx)
        job_id = _compute_job_id(owner, schedule, command, source, source_file, idx)

        parsed_jobs.append({
            "id": job_id,
            "owner": owner,
            "schedule": schedule,
            "minute": minute,
            "hour": hour,
            "day_of_month": dom,
            "month": month,
            "day_of_week": dow,
            "special_expression": special_expr,
            "command": command,
            "comment": pending_comment,
            "enabled": not is_disabled,
            "source": source,
            "source_file": source_file,
            "line_number": idx + 1,
            "original_hash": job_hash,
            "is_editable": source == "USER_CRONTAB",
        })

        pending_comment = None

    return parsed_jobs


# -----------------------------------------------------------------------------
# Allowlisted Operation Handlers
# -----------------------------------------------------------------------------

async def handle_cron_list(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Operation: cron.list
    Safely discovers and parses cron jobs from user crontabs and system sources.
    Payload: {"users": Optional[List[str]], "include_system": bool}
    """
    target_users = payload.get("users")
    include_system = payload.get("include_system", True)

    jobs: List[Dict[str, Any]] = []

    # 1. Discover user crontabs
    if target_users is None:
        # Query local OS accounts that can have crontabs (UID >= 1000 + root)
        users_to_check: List[str] = []
        for entry in pwd.getpwall():
            if entry.pw_name == "root" or (entry.pw_uid >= 1000 and entry.pw_name != "nobody"):
                users_to_check.append(entry.pw_name)
    else:
        users_to_check = [_validate_agent_user(u) for u in target_users]

    for u in sorted(set(users_to_check)):
        try:
            content = await _read_user_crontab_content(u)
            if content.strip():
                spool_file = _get_spool_path(u)
                user_jobs = _parse_crontab_lines(content, owner=u, source="USER_CRONTAB", source_file=spool_file)
                jobs.extend(user_jobs)
        except Exception as exc:
            logger.warning(f"Failed to read crontab for user '{u}': {exc}")

    # 2. System sources if requested
    if include_system:
        # /etc/crontab (6th field is user)
        if os.path.isfile("/etc/crontab"):
            try:
                with open("/etc/crontab", "r", encoding="utf-8", errors="replace") as f:
                    lines = f.read().splitlines()
                for idx, line in enumerate(lines):
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#") or "=" in stripped.split()[0]:
                        continue
                    tokens = stripped.split(maxsplit=6)
                    if len(tokens) >= 7:
                        m, h, dom, mon, dow, s_user, s_cmd = tokens
                        sched = f"{m} {h} {dom} {mon} {dow}"
                        job_id = _compute_job_id(s_user, sched, s_cmd, "SYSTEM_CRONTAB", "/etc/crontab", idx)
                        job_hash = _compute_job_hash(s_user, sched, s_cmd, idx)
                        jobs.append({
                            "id": job_id,
                            "owner": s_user,
                            "schedule": sched,
                            "minute": m,
                            "hour": h,
                            "day_of_month": dom,
                            "month": mon,
                            "day_of_week": dow,
                            "special_expression": None,
                            "command": s_cmd,
                            "comment": None,
                            "enabled": True,
                            "source": "SYSTEM_CRONTAB",
                            "source_file": "/etc/crontab",
                            "line_number": idx + 1,
                            "original_hash": job_hash,
                            "is_editable": False,
                        })
            except Exception as exc:
                logger.warning(f"Error reading /etc/crontab: {exc}")

        # /etc/cron.d/*
        cron_d = "/etc/cron.d"
        if os.path.isdir(cron_d):
            try:
                for fname in sorted(os.listdir(cron_d)):
                    if fname.startswith(".") or fname.endswith("~") or fname.endswith(".dpkg-old"):
                        continue
                    fpath = os.path.join(cron_d, fname)
                    if not os.path.isfile(fpath):
                        continue
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                            d_lines = f.read().splitlines()
                        for idx, line in enumerate(d_lines):
                            stripped = line.strip()
                            if not stripped or stripped.startswith("#") or "=" in stripped.split()[0]:
                                continue
                            tokens = stripped.split(maxsplit=6)
                            if len(tokens) >= 7:
                                m, h, dom, mon, dow, d_user, d_cmd = tokens
                                sched = f"{m} {h} {dom} {mon} {dow}"
                                job_id = _compute_job_id(d_user, sched, d_cmd, "CRON_D_DIRECTORY", fpath, idx)
                                job_hash = _compute_job_hash(d_user, sched, d_cmd, idx)
                                jobs.append({
                                    "id": job_id,
                                    "owner": d_user,
                                    "schedule": sched,
                                    "minute": m,
                                    "hour": h,
                                    "day_of_month": dom,
                                    "month": mon,
                                    "day_of_week": dow,
                                    "special_expression": None,
                                    "command": d_cmd,
                                    "comment": f"From /etc/cron.d/{fname}",
                                    "enabled": True,
                                    "source": "CRON_D_DIRECTORY",
                                    "source_file": fpath,
                                    "line_number": idx + 1,
                                    "original_hash": job_hash,
                                    "is_editable": False,
                                })
                    except Exception as exc:
                        logger.warning(f"Error reading cron.d file {fpath}: {exc}")
            except Exception as exc:
                logger.warning(f"Error listing /etc/cron.d: {exc}")

        # Periodic directories
        periodic_specs = [
            ("/etc/cron.hourly", "@hourly", "0 * * * *"),
            ("/etc/cron.daily", "@daily", "0 0 * * *"),
            ("/etc/cron.weekly", "@weekly", "0 0 * * 0"),
            ("/etc/cron.monthly", "@monthly", "0 0 1 * *"),
        ]
        for p_dir, p_special, p_sched in periodic_specs:
            if os.path.isdir(p_dir):
                try:
                    for sname in sorted(os.listdir(p_dir)):
                        if sname.startswith(".") or sname.endswith("~") or sname.endswith(".dpkg-old"):
                            continue
                        spath = os.path.join(p_dir, sname)
                        if not os.path.isfile(spath) or not os.access(spath, os.X_OK):
                            continue
                        job_id = _compute_job_id("root", p_sched, spath, "PERIODIC_DIRECTORY", spath, 0)
                        job_hash = _compute_job_hash("root", p_sched, spath, 0)
                        jobs.append({
                            "id": job_id,
                            "owner": "root",
                            "schedule": p_sched,
                            "minute": p_sched.split()[0],
                            "hour": p_sched.split()[1],
                            "day_of_month": p_sched.split()[2],
                            "month": p_sched.split()[3],
                            "day_of_week": p_sched.split()[4],
                            "special_expression": p_special,
                            "command": spath,
                            "comment": f"Periodic executable in {p_dir}",
                            "enabled": True,
                            "source": "PERIODIC_DIRECTORY",
                            "source_file": spath,
                            "line_number": None,
                            "original_hash": job_hash,
                            "is_editable": False,
                        })
                except Exception as exc:
                    logger.warning(f"Error reading periodic directory {p_dir}: {exc}")

    return {"jobs": jobs, "total": len(jobs)}


async def handle_cron_create(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Operation: cron.create
    Safely creates a new cron job for a validated local user account.
    Appends the job while preserving all existing crontab comments, lines, and settings.
    """
    owner = _validate_agent_user(payload.get("owner"))
    schedule = _validate_agent_schedule(payload.get("schedule"))
    command = _validate_agent_command(payload.get("command"))
    comment = _validate_agent_comment(payload.get("comment"))
    enabled = bool(payload.get("enabled", True))

    existing_content = await _read_user_crontab_content(owner)
    lines = existing_content.splitlines()

    new_block: List[str] = []
    if lines and lines[-1].strip() != "":
        new_block.append("")

    if comment:
        new_block.append(f"# {comment}")

    if enabled:
        new_block.append(f"{schedule} {command}")
    else:
        new_block.append(f"# DISABLED: {schedule} {command}")

    updated_content = existing_content
    if updated_content and not updated_content.endswith("\n"):
        updated_content += "\n"
    updated_content += "\n".join(new_block) + "\n"

    await _write_user_crontab_content(owner, updated_content)

    # Return newly created job representation
    spool_file = _get_spool_path(owner)
    new_idx = len(lines) + len(new_block) - 1
    job_hash = _compute_job_hash(owner, schedule, command, new_idx)
    job_id = _compute_job_id(owner, schedule, command, "USER_CRONTAB", spool_file, new_idx)

    tokens = schedule.split() if not schedule.startswith("@") else []
    return {
        "success": True,
        "job": {
            "id": job_id,
            "owner": owner,
            "schedule": schedule,
            "minute": tokens[0] if len(tokens) == 5 else "",
            "hour": tokens[1] if len(tokens) == 5 else "",
            "day_of_month": tokens[2] if len(tokens) == 5 else "",
            "month": tokens[3] if len(tokens) == 5 else "",
            "day_of_week": tokens[4] if len(tokens) == 5 else "",
            "special_expression": schedule if schedule.startswith("@") else None,
            "command": command,
            "comment": comment,
            "enabled": enabled,
            "source": "USER_CRONTAB",
            "source_file": spool_file,
            "line_number": new_idx + 1,
            "original_hash": job_hash,
            "is_editable": True,
        }
    }


async def handle_cron_update(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Operation: cron.update
    Safely updates an existing user cron job with optimistic concurrency check.
    Preserves all other comments, lines, and unmanaged entries.
    """
    owner = _validate_agent_user(payload.get("owner"))
    schedule = _validate_agent_schedule(payload.get("schedule"))
    command = _validate_agent_command(payload.get("command"))
    comment = _validate_agent_comment(payload.get("comment"))
    enabled = bool(payload.get("enabled", True))
    expected_hash = payload.get("expected_hash")
    target_id = payload.get("id")

    existing_content = await _read_user_crontab_content(owner)
    spool_file = _get_spool_path(owner)
    current_jobs = _parse_crontab_lines(existing_content, owner=owner, source="USER_CRONTAB", source_file=spool_file)

    target_job: Optional[Dict[str, Any]] = None
    for j in current_jobs:
        if (target_id and j["id"] == target_id) or (expected_hash and j["original_hash"] == expected_hash):
            target_job = j
            break

    if not target_job:
        raise ValueError("Target cron job not found in crontab or was modified concurrently (Conflict)")

    if expected_hash and target_job["original_hash"] != expected_hash:
        raise ValueError("Optimistic concurrency failure: crontab job has changed since retrieval (Conflict)")

    target_line_idx = (target_job["line_number"] or 1) - 1
    lines = existing_content.splitlines()

    if target_line_idx >= len(lines):
        raise ValueError("Crontab layout shifted; please refresh before updating")

    # If previous line was an attached comment, update it or retain it
    if comment:
        if target_line_idx > 0 and lines[target_line_idx - 1].strip().startswith("#"):
            lines[target_line_idx - 1] = f"# {comment}"
        else:
            lines.insert(target_line_idx, f"# {comment}")
            target_line_idx += 1

    # Replace target job line
    if enabled:
        lines[target_line_idx] = f"{schedule} {command}"
    else:
        lines[target_line_idx] = f"# DISABLED: {schedule} {command}"

    new_content = "\n".join(lines) + "\n"
    await _write_user_crontab_content(owner, new_content)

    new_hash = _compute_job_hash(owner, schedule, command, target_line_idx)
    new_id = _compute_job_id(owner, schedule, command, "USER_CRONTAB", spool_file, target_line_idx)
    tokens = schedule.split() if not schedule.startswith("@") else []

    return {
        "success": True,
        "job": {
            "id": new_id,
            "owner": owner,
            "schedule": schedule,
            "minute": tokens[0] if len(tokens) == 5 else "",
            "hour": tokens[1] if len(tokens) == 5 else "",
            "day_of_month": tokens[2] if len(tokens) == 5 else "",
            "month": tokens[3] if len(tokens) == 5 else "",
            "day_of_week": tokens[4] if len(tokens) == 5 else "",
            "special_expression": schedule if schedule.startswith("@") else None,
            "command": command,
            "comment": comment,
            "enabled": enabled,
            "source": "USER_CRONTAB",
            "source_file": spool_file,
            "line_number": target_line_idx + 1,
            "original_hash": new_hash,
            "is_editable": True,
        }
    }


async def handle_cron_delete(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Operation: cron.delete
    Safely deletes an identified cron job from user crontab.
    Preserves all other entries, comments, and environment lines.
    """
    owner = _validate_agent_user(payload.get("owner"))
    expected_hash = payload.get("expected_hash")
    target_id = payload.get("id")

    existing_content = await _read_user_crontab_content(owner)
    spool_file = _get_spool_path(owner)
    current_jobs = _parse_crontab_lines(existing_content, owner=owner, source="USER_CRONTAB", source_file=spool_file)

    target_job: Optional[Dict[str, Any]] = None
    for j in current_jobs:
        if (target_id and j["id"] == target_id) or (expected_hash and j["original_hash"] == expected_hash):
            target_job = j
            break

    if not target_job:
        raise ValueError("Target cron job not found in user crontab")

    if expected_hash and target_job["original_hash"] != expected_hash:
        raise ValueError("Optimistic concurrency failure: crontab job has changed since retrieval (Conflict)")

    target_line_idx = (target_job["line_number"] or 1) - 1
    lines = existing_content.splitlines()

    if target_line_idx < len(lines):
        # Remove target line
        del lines[target_line_idx]
        # If preceding line was an attached comment, clean it up if standalone
        if target_line_idx > 0 and lines[target_line_idx - 1].strip().startswith("#"):
            del lines[target_line_idx - 1]

    new_content = "\n".join(lines) + ("\n" if lines else "")
    await _write_user_crontab_content(owner, new_content)

    return {
        "success": True,
        "deleted_id": target_job["id"],
        "owner": owner,
        "message": f"Cron job '{target_job['id']}' successfully removed from {owner}'s crontab",
    }
