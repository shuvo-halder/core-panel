import hashlib
import math
import os
import pwd
from typing import Any, Dict, List, Optional

from backend.app.core.errors import AppError, ConflictError, NotFoundError
from backend.app.core.logging import logger
from backend.app.core.validators import (
    SPECIAL_CRON_EXPRESSIONS,
    validate_cron_command,
    validate_cron_comment,
    validate_cron_schedule,
    validate_cron_username,
)
from backend.app.ipc.client import ipc_client
from backend.app.linux.contracts import (
    CronJob,
    CronListResult,
    CronOverview,
    CronSource,
    ICronManager,
)


def translate_cron_schedule_to_human(schedule: str) -> str:
    """Translates a validated cron expression into a human-readable summary string."""
    clean = schedule.strip()
    if clean.startswith("@"):
        mapping = {
            "@reboot": "Run once at system startup",
            "@hourly": "Every hour at minute 0",
            "@daily": "Every day at midnight (00:00)",
            "@midnight": "Every day at midnight (00:00)",
            "@weekly": "Every Sunday at midnight (00:00)",
            "@monthly": "First day of every month at midnight (00:00)",
            "@yearly": "January 1st of every year at midnight",
            "@annually": "January 1st of every year at midnight",
        }
        return mapping.get(clean.lower(), clean)

    fields = clean.split()
    if len(fields) != 5:
        return clean

    m, h, dom, mon, dow = fields

    if clean == "* * * * *":
        return "Every minute"
    if m.startswith("*/") and h == "*" and dom == "*" and mon == "*" and dow == "*":
        return f"Every {m[2:]} minutes"
    if m.isdigit() and h == "*" and dom == "*" and mon == "*" and dow == "*":
        return f"Every hour at minute {m}"
    if m.isdigit() and h.isdigit() and dom == "*" and mon == "*" and dow == "*":
        return f"Daily at {int(h):02d}:{int(m):02d}"
    if m.isdigit() and h.isdigit() and dom == "*" and mon == "*" and dow in ("0", "7", "SUN"):
        return f"Every Sunday at {int(h):02d}:{int(m):02d}"
    if m.isdigit() and h.isdigit() and dom == "1" and mon == "*" and dow == "*":
        return f"First day of each month at {int(h):02d}:{int(m):02d}"
    if m.isdigit() and h.isdigit() and dom == "*" and mon == "*" and dow == "1-5":
        return f"Monday through Friday at {int(h):02d}:{int(m):02d}"

    # General descriptive breakdown
    parts = []
    if m == "*":
        parts.append("every minute")
    elif m.startswith("*/"):
        parts.append(f"every {m[2:]} mins")
    else:
        parts.append(f"min {m}")

    if h == "*":
        parts.append("of every hour")
    elif h.startswith("*/"):
        parts.append(f"every {h[2:]} hours")
    else:
        parts.append(f"at hour {h}")

    if dom != "*":
        parts.append(f"on day-of-month {dom}")
    if mon != "*":
        parts.append(f"in month {mon}")
    if dow != "*":
        parts.append(f"on day-of-week {dow}")

    return " ".join(parts)


class LinuxCronManager(ICronManager):
    """
    Production implementation of ICronManager.
    Coordinates between the unprivileged control plane, local OS metadata,
    and the privileged CoreAgent IPC boundary for safe crontab management.
    """

    async def _fetch_all_raw_jobs(self) -> List[CronJob]:
        """Queries CoreAgent over IPC for current cron jobs, with fallback to local discovery."""
        try:
            res = await ipc_client.execute(
                operation="cron.list",
                payload={"users": None, "include_system": True},
            )
            raw_list = res.get("jobs", [])
            cron_jobs: List[CronJob] = []
            for r in raw_list:
                cron_jobs.append(
                    CronJob(
                        id=r["id"],
                        owner=r["owner"],
                        schedule=r["schedule"],
                        minute=r.get("minute", ""),
                        hour=r.get("hour", ""),
                        day_of_month=r.get("day_of_month", ""),
                        month=r.get("month", ""),
                        day_of_week=r.get("day_of_week", ""),
                        special_expression=r.get("special_expression"),
                        command=r["command"],
                        comment=r.get("comment"),
                        enabled=r.get("enabled", True),
                        source=r.get("source", CronSource.USER_CRONTAB),
                        source_file=r.get("source_file"),
                        line_number=r.get("line_number"),
                        description=translate_cron_schedule_to_human(r["schedule"]),
                        is_editable=r.get("is_editable", True),
                        original_hash=r.get("original_hash"),
                    )
                )
            return cron_jobs
        except Exception as exc:
            logger.info(f"CoreAgent IPC unavailable for cron.list ({exc}); falling back to local inspection")
            return self._local_fallback_discovery()

    def _local_fallback_discovery(self) -> List[CronJob]:
        """Local direct unprivileged discovery of system and periodic crontabs."""
        jobs: List[CronJob] = []

        # 1. /etc/crontab
        if os.path.isfile("/etc/crontab"):
            try:
                with open("/etc/crontab", "r", encoding="utf-8", errors="replace") as f:
                    for idx, line in enumerate(f):
                        stripped = line.strip()
                        if not stripped or stripped.startswith("#") or "=" in stripped.split()[0]:
                            continue
                        tokens = stripped.split(maxsplit=6)
                        if len(tokens) >= 7:
                            m, h, dom, mon, dow, s_user, s_cmd = tokens
                            sched = f"{m} {h} {dom} {mon} {dow}"
                            raw_id = f"SYSTEM_CRONTAB:/etc/crontab:{s_user}:{sched}:{s_cmd}:{idx}".encode()
                            jid = f"cron_{hashlib.sha256(raw_id).hexdigest()[:12]}"
                            jhash = hashlib.sha256(f"{s_user}:{sched}:{s_cmd}:{idx}".encode()).hexdigest()[:16]
                            jobs.append(
                                CronJob(
                                    id=jid,
                                    owner=s_user,
                                    schedule=sched,
                                    minute=m,
                                    hour=h,
                                    day_of_month=dom,
                                    month=mon,
                                    day_of_week=dow,
                                    command=s_cmd,
                                    enabled=True,
                                    source=CronSource.SYSTEM_CRONTAB,
                                    source_file="/etc/crontab",
                                    line_number=idx + 1,
                                    description=translate_cron_schedule_to_human(sched),
                                    is_editable=False,
                                    original_hash=jhash,
                                )
                            )
            except Exception as e:
                logger.warning(f"Fallback reading /etc/crontab failed: {e}")

        # 2. /etc/cron.d/*
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
                            for idx, line in enumerate(f):
                                stripped = line.strip()
                                if not stripped or stripped.startswith("#") or "=" in stripped.split()[0]:
                                    continue
                                tokens = stripped.split(maxsplit=6)
                                if len(tokens) >= 7:
                                    m, h, dom, mon, dow, d_user, d_cmd = tokens
                                    sched = f"{m} {h} {dom} {mon} {dow}"
                                    raw_id = f"CRON_D_DIRECTORY:{fpath}:{d_user}:{sched}:{d_cmd}:{idx}".encode()
                                    jid = f"cron_{hashlib.sha256(raw_id).hexdigest()[:12]}"
                                    jhash = hashlib.sha256(f"{d_user}:{sched}:{d_cmd}:{idx}".encode()).hexdigest()[:16]
                                    jobs.append(
                                        CronJob(
                                            id=jid,
                                            owner=d_user,
                                            schedule=sched,
                                            minute=m,
                                            hour=h,
                                            day_of_month=dom,
                                            month=mon,
                                            day_of_week=dow,
                                            command=d_cmd,
                                            comment=f"From /etc/cron.d/{fname}",
                                            enabled=True,
                                            source=CronSource.CRON_D_DIRECTORY,
                                            source_file=fpath,
                                            line_number=idx + 1,
                                            description=translate_cron_schedule_to_human(sched),
                                            is_editable=False,
                                            original_hash=jhash,
                                        )
                                    )
                    except Exception as e:
                        logger.warning(f"Fallback reading {fpath} failed: {e}")
            except Exception as e:
                logger.warning(f"Fallback listing /etc/cron.d failed: {e}")

        # 3. Periodic directories
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
                        jid = f"cron_{hashlib.sha256(f'PERIODIC_DIRECTORY:{spath}:root:{p_sched}:{spath}:0'.encode()).hexdigest()[:12]}"
                        jhash = hashlib.sha256(f"root:{p_sched}:{spath}:0".encode()).hexdigest()[:16]
                        jobs.append(
                            CronJob(
                                id=jid,
                                owner="root",
                                schedule=p_sched,
                                minute=p_sched.split()[0],
                                hour=p_sched.split()[1],
                                day_of_month=p_sched.split()[2],
                                month=p_sched.split()[3],
                                day_of_week=p_sched.split()[4],
                                special_expression=p_special,
                                command=spath,
                                comment=f"Periodic executable in {p_dir}",
                                enabled=True,
                                source=CronSource.PERIODIC_DIRECTORY,
                                source_file=spath,
                                description=translate_cron_schedule_to_human(p_sched),
                                is_editable=False,
                                original_hash=jhash,
                            )
                        )
                except Exception as e:
                    logger.warning(f"Fallback reading periodic directory {p_dir} failed: {e}")

        return jobs

    async def get_overview(self) -> CronOverview:
        """Computes summary KPI metrics for all discovered cron jobs."""
        all_jobs = await self._fetch_all_raw_jobs()
        active_jobs = [j for j in all_jobs if j.enabled]
        disabled_jobs = [j for j in all_jobs if not j.enabled]

        user_jobs = [j for j in all_jobs if j.source == CronSource.USER_CRONTAB]
        system_jobs = [j for j in all_jobs if j.source == CronSource.SYSTEM_CRONTAB]
        cron_d_jobs = [j for j in all_jobs if j.source == CronSource.CRON_D_DIRECTORY]
        periodic_jobs = [j for j in all_jobs if j.source == CronSource.PERIODIC_DIRECTORY]

        users_with_crontabs = len(set(j.owner for j in user_jobs))

        return CronOverview(
            total_jobs=len(all_jobs),
            active_jobs=len(active_jobs),
            disabled_jobs=len(disabled_jobs),
            users_with_crontabs=users_with_crontabs,
            user_jobs_count=len(user_jobs),
            system_jobs_count=len(system_jobs),
            cron_d_jobs_count=len(cron_d_jobs),
            periodic_jobs_count=len(periodic_jobs),
            available_sources=[
                CronSource.USER_CRONTAB,
                CronSource.SYSTEM_CRONTAB,
                CronSource.CRON_D_DIRECTORY,
                CronSource.PERIODIC_DIRECTORY,
            ],
        )

    async def list_jobs(
        self,
        page: int = 1,
        page_size: int = 50,
        owner: Optional[str] = None,
        source: Optional[str] = None,
        enabled: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> CronListResult:
        """Returns paginated, filtered cron job entries."""
        all_jobs = await self._fetch_all_raw_jobs()

        filtered: List[CronJob] = all_jobs

        if owner:
            clean_owner = owner.strip().lower()
            filtered = [j for j in filtered if j.owner.lower() == clean_owner]

        if source:
            clean_source = source.strip().upper()
            filtered = [j for j in filtered if j.source.upper() == clean_source]

        if enabled is not None:
            filtered = [j for j in filtered if j.enabled == enabled]

        if search:
            query = search.strip().lower()
            filtered = [
                j for j in filtered
                if query in j.command.lower()
                or (j.comment and query in j.comment.lower())
                or query in j.schedule.lower()
                or query in j.owner.lower()
                or (j.source_file and query in j.source_file.lower())
            ]

        total = len(filtered)
        p = max(1, page)
        ps = max(1, min(100, page_size))
        total_pages = math.ceil(total / ps) if total > 0 else 1

        start = (p - 1) * ps
        end = start + ps
        items = filtered[start:end]

        return CronListResult(
            items=items,
            total=total,
            page=p,
            page_size=ps,
            total_pages=total_pages,
        )

    async def get_job(self, job_id: str) -> Optional[CronJob]:
        """Retrieves an individual cron job by stable ID."""
        all_jobs = await self._fetch_all_raw_jobs()
        for j in all_jobs:
            if j.id == job_id:
                return j
        return None

    async def create_job(
        self,
        owner: str,
        schedule: str,
        command: str,
        comment: Optional[str] = None,
        enabled: bool = True,
    ) -> CronJob:
        """Creates a new cron job entry via CoreAgent IPC."""
        clean_user = validate_cron_username(owner)
        clean_sched = validate_cron_schedule(schedule)
        clean_cmd = validate_cron_command(command)
        clean_comment = validate_cron_comment(comment)

        try:
            res = await ipc_client.execute(
                operation="cron.create",
                payload={
                    "owner": clean_user,
                    "schedule": clean_sched,
                    "command": clean_cmd,
                    "comment": clean_comment,
                    "enabled": enabled,
                },
            )
            job_data = res.get("job")
            if not job_data:
                raise AppError("CoreAgent did not return created job data")

            return CronJob(
                id=job_data["id"],
                owner=job_data["owner"],
                schedule=job_data["schedule"],
                minute=job_data.get("minute", ""),
                hour=job_data.get("hour", ""),
                day_of_month=job_data.get("day_of_month", ""),
                month=job_data.get("month", ""),
                day_of_week=job_data.get("day_of_week", ""),
                special_expression=job_data.get("special_expression"),
                command=job_data["command"],
                comment=job_data.get("comment"),
                enabled=job_data.get("enabled", True),
                source=CronSource.USER_CRONTAB,
                source_file=job_data.get("source_file"),
                line_number=job_data.get("line_number"),
                description=translate_cron_schedule_to_human(job_data["schedule"]),
                is_editable=True,
                original_hash=job_data.get("original_hash"),
            )
        except ValueError as exc:
            raise ConflictError(str(exc))
        except Exception as exc:
            if "Conflict" in str(exc) or "not found" in str(exc):
                raise ConflictError(str(exc))
            raise

    async def update_job(
        self,
        job_id: str,
        owner: str,
        schedule: str,
        command: str,
        comment: Optional[str] = None,
        enabled: bool = True,
        expected_hash: Optional[str] = None,
    ) -> CronJob:
        """Updates an existing user cron job with optimistic concurrency check."""
        clean_user = validate_cron_username(owner)
        clean_sched = validate_cron_schedule(schedule)
        clean_cmd = validate_cron_command(command)
        clean_comment = validate_cron_comment(comment)

        try:
            res = await ipc_client.execute(
                operation="cron.update",
                payload={
                    "id": job_id,
                    "owner": clean_user,
                    "schedule": clean_sched,
                    "command": clean_cmd,
                    "comment": clean_comment,
                    "enabled": enabled,
                    "expected_hash": expected_hash,
                },
            )
            job_data = res.get("job")
            if not job_data:
                raise AppError("CoreAgent did not return updated job data")

            return CronJob(
                id=job_data["id"],
                owner=job_data["owner"],
                schedule=job_data["schedule"],
                minute=job_data.get("minute", ""),
                hour=job_data.get("hour", ""),
                day_of_month=job_data.get("day_of_month", ""),
                month=job_data.get("month", ""),
                day_of_week=job_data.get("day_of_week", ""),
                special_expression=job_data.get("special_expression"),
                command=job_data["command"],
                comment=job_data.get("comment"),
                enabled=job_data.get("enabled", True),
                source=CronSource.USER_CRONTAB,
                source_file=job_data.get("source_file"),
                line_number=job_data.get("line_number"),
                description=translate_cron_schedule_to_human(job_data["schedule"]),
                is_editable=True,
                original_hash=job_data.get("original_hash"),
            )
        except ValueError as exc:
            err_msg = str(exc)
            if "not found" in err_msg.lower():
                raise NotFoundError(err_msg)
            raise ConflictError(err_msg)
        except Exception as exc:
            if "Conflict" in str(exc):
                raise ConflictError(str(exc))
            raise

    async def delete_job(
        self,
        job_id: str,
        owner: str,
        expected_hash: Optional[str] = None,
    ) -> bool:
        """Safely deletes an identified cron job from user crontab."""
        clean_user = validate_cron_username(owner)

        try:
            res = await ipc_client.execute(
                operation="cron.delete",
                payload={
                    "id": job_id,
                    "owner": clean_user,
                    "expected_hash": expected_hash,
                },
            )
            return bool(res.get("success", False))
        except ValueError as exc:
            err_msg = str(exc)
            if "not found" in err_msg.lower():
                raise NotFoundError(err_msg)
            raise ConflictError(err_msg)
        except Exception as exc:
            if "Conflict" in str(exc):
                raise ConflictError(str(exc))
            raise

    def list_eligible_users(self) -> List[Dict[str, Any]]:
        """Lists valid local OS user accounts that can possess user crontabs."""
        results: List[Dict[str, Any]] = []
        for entry in pwd.getpwall():
            if entry.pw_name == "root" or (entry.pw_uid >= 1000 and entry.pw_name != "nobody"):
                results.append({
                    "username": entry.pw_name,
                    "uid": entry.pw_uid,
                    "gid": entry.pw_gid,
                    "home": entry.pw_dir,
                    "shell": entry.pw_shell,
                })
        return sorted(results, key=lambda u: (0 if u["username"] == "root" else 1, u["username"]))


cron_manager = LinuxCronManager()
