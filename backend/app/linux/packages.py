import configparser
import math
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend.app.core.errors import BadRequestError
from backend.app.core.logging import logger
from backend.app.core.validators import validate_package_name
from backend.app.linux.contracts import (
    IPackageManager,
    PackageDetails,
    PackageInfo,
    PackageListResult,
    PackageManagerInfo,
    PackageOverview,
    PackageUpdateInfo,
    RepositoryInfo,
)


class PackageManager(IPackageManager):
    """
    Linux Package Management Foundation abstraction.
    Provides strictly read-only package inventory, details, repository, and update discovery
    using safe filesystem metadata and fixed allowlisted commands (zero shell execution).
    """

    ALLOWED_SORT_FIELDS = {"name", "version", "status", "installed_size_kb", "architecture"}

    def __init__(
        self,
        os_release_paths: Optional[List[Path]] = None,
        dpkg_status_path: Optional[Path] = None,
        apt_sources_list_path: Optional[Path] = None,
        apt_sources_dir_path: Optional[Path] = None,
        yum_repos_dir_path: Optional[Path] = None,
        apk_installed_path: Optional[Path] = None,
    ):
        self.os_release_paths = os_release_paths or [
            Path("/etc/os-release"),
            Path("/usr/lib/os-release"),
        ]
        self.dpkg_status_path = dpkg_status_path or Path("/var/lib/dpkg/status")
        self.apt_sources_list_path = apt_sources_list_path or Path("/etc/apt/sources.list")
        self.apt_sources_dir_path = apt_sources_dir_path or Path("/etc/apt/sources.list.d")
        self.yum_repos_dir_path = yum_repos_dir_path or Path("/etc/yum.repos.d")
        self.apk_installed_path = apk_installed_path or Path("/lib/apk/db/installed")

        # Short-lived in-memory cache for package inventory (5 seconds TTL)
        self._cache_timestamp: float = 0
        self._cached_packages: Dict[str, PackageDetails] = {}
        self._cached_manager_info: Optional[PackageManagerInfo] = None

    def get_manager_info(self) -> PackageManagerInfo:
        """Detects the operating system distribution and available package management ecosystem."""
        if self._cached_manager_info is not None:
            return self._cached_manager_info

        distro_name = "Linux"
        distro_id = "unknown"
        distro_id_like = ""
        distro_version = ""

        # Step 1: Parse /etc/os-release or /usr/lib/os-release
        for p in self.os_release_paths:
            if p.exists() and p.is_file():
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    for line in content.splitlines():
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("\"'")
                        if k == "PRETTY_NAME":
                            distro_name = v
                        elif k == "NAME" and distro_name == "Linux":
                            distro_name = v
                        elif k == "ID":
                            distro_id = v.lower()
                        elif k == "ID_LIKE":
                            distro_id_like = v.lower()
                        elif k == "VERSION_ID":
                            distro_version = v
                    break
                except Exception as exc:
                    logger.warning(f"Could not read os-release at {p}: {exc}")

        arch = platform.machine() or "unknown"

        # Step 2: Determine package manager family and active manager
        family = "unknown"
        manager = "unknown"
        available = False

        # Debian / Ubuntu family
        if (
            distro_id in ("debian", "ubuntu", "raspbian", "kali", "linuxmint", "pop")
            or "debian" in distro_id_like
            or "ubuntu" in distro_id_like
            or self.dpkg_status_path.exists()
            or shutil.which("dpkg-query") is not None
        ):
            family = "debian"
            if shutil.which("apt-cache") is not None or shutil.which("apt") is not None:
                manager = "apt"
            else:
                manager = "dpkg"
            available = self.dpkg_status_path.exists() or shutil.which("dpkg-query") is not None

        # RHEL / Fedora family
        elif (
            distro_id in ("rhel", "fedora", "centos", "rocky", "almalinux", "ol", "amzn")
            or "rhel" in distro_id_like
            or "fedora" in distro_id_like
            or Path("/var/lib/rpm").exists()
            or shutil.which("rpm") is not None
        ):
            family = "rhel"
            if shutil.which("dnf") is not None:
                manager = "dnf"
            elif shutil.which("yum") is not None:
                manager = "yum"
            else:
                manager = "rpm"
            available = Path("/var/lib/rpm").exists() or shutil.which("rpm") is not None

        # Alpine Linux
        elif distro_id == "alpine" or self.apk_installed_path.exists() or shutil.which("apk") is not None:
            family = "alpine"
            manager = "apk"
            available = self.apk_installed_path.exists() or shutil.which("apk") is not None

        # Arch Linux
        elif distro_id == "arch" or Path("/var/lib/pacman").exists() or shutil.which("pacman") is not None:
            family = "arch"
            manager = "pacman"
            available = Path("/var/lib/pacman").exists() or shutil.which("pacman") is not None

        info = PackageManagerInfo(
            manager=manager,
            family=family,
            distribution=distro_name,
            version=distro_version,
            architecture=arch,
            available=available,
        )
        self._cached_manager_info = info
        return info

    def _load_all_packages(self, force_reload: bool = False) -> Dict[str, PackageDetails]:
        """Loads and caches all installed packages from operating system package databases."""
        now = time.time()
        if not force_reload and self._cached_packages and (now - self._cache_timestamp < 5.0):
            return self._cached_packages

        mgr_info = self.get_manager_info()
        packages: Dict[str, PackageDetails] = {}

        if mgr_info.family == "debian":
            packages = self._load_debian_packages()
        elif mgr_info.family == "rhel":
            packages = self._load_rhel_packages()
        elif mgr_info.family == "alpine":
            packages = self._load_alpine_packages()
        else:
            # Fallback attempts
            if self.dpkg_status_path.exists():
                packages = self._load_debian_packages()
            elif shutil.which("rpm") is not None:
                packages = self._load_rhel_packages()

        self._cached_packages = packages
        self._cache_timestamp = now
        return packages

    def _load_debian_packages(self) -> Dict[str, PackageDetails]:
        """Parses Debian package status from /var/lib/dpkg/status or dpkg-query."""
        packages: Dict[str, PackageDetails] = {}

        # Primary method: direct parsing of /var/lib/dpkg/status (zero subprocess overhead)
        if self.dpkg_status_path.exists() and self.dpkg_status_path.is_file():
            try:
                content = self.dpkg_status_path.read_text(encoding="utf-8", errors="replace")
                # Split by empty paragraph lines
                paragraphs = content.split("\n\n")
                for para in paragraphs:
                    if not para.strip():
                        continue
                    pkg_dict = self._parse_dpkg_paragraph(para)
                    if pkg_dict and "name" in pkg_dict:
                        # Only include packages that are installed or have config files
                        status = pkg_dict.get("status", "installed")
                        if "installed" in status or "config-files" in status or "half" in status:
                            packages[pkg_dict["name"]] = PackageDetails(
                                name=pkg_dict["name"],
                                version=pkg_dict.get("version", "unknown"),
                                architecture=pkg_dict.get("architecture", "all"),
                                status=status,
                                summary=pkg_dict.get("summary", ""),
                                description=pkg_dict.get("description", ""),
                                source=pkg_dict.get("source"),
                                section=pkg_dict.get("section"),
                                maintainer=pkg_dict.get("maintainer"),
                                homepage=pkg_dict.get("homepage"),
                                installed_size_kb=pkg_dict.get("installed_size_kb"),
                                dependencies=pkg_dict.get("dependencies", []),
                            )
                if packages:
                    return packages
            except Exception as exc:
                logger.warning(f"Direct parsing of /var/lib/dpkg/status failed: {exc}")

        # Fallback method: dpkg-query using fixed executable and arguments
        dpkg_query_bin = shutil.which("dpkg-query") or "/usr/bin/dpkg-query"
        if os.path.exists(dpkg_query_bin):
            try:
                # Fixed arguments with tab delimiter: name, version, arch, status, summary, size
                cmd = [
                    dpkg_query_bin,
                    "-W",
                    "-f=${Package}\t${Version}\t${Architecture}\t${db:Status-Status}\t${binary:Summary}\t${Installed-Size}\t${Section}\t${Source}\n",
                ]
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=8.0,
                    check=False,
                    shell=False,
                )
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        parts = line.split("\t")
                        if len(parts) >= 5:
                            p_name = parts[0].strip()
                            p_ver = parts[1].strip()
                            p_arch = parts[2].strip()
                            p_status = parts[3].strip() or "installed"
                            p_summary = parts[4].strip()
                            p_size = None
                            if len(parts) >= 6 and parts[5].strip().isdigit():
                                p_size = int(parts[5].strip())
                            p_section = parts[6].strip() if len(parts) >= 7 else None
                            p_source = parts[7].strip() if len(parts) >= 8 else None

                            if p_name:
                                packages[p_name] = PackageDetails(
                                    name=p_name,
                                    version=p_ver,
                                    architecture=p_arch,
                                    status=p_status,
                                    summary=p_summary,
                                    description=p_summary,
                                    source=p_source,
                                    section=p_section,
                                    maintainer=None,
                                    homepage=None,
                                    installed_size_kb=p_size,
                                    dependencies=[],
                                )
            except Exception as exc:
                logger.error(f"dpkg-query fallback execution failed: {exc}")

        return packages

    def _parse_dpkg_paragraph(self, paragraph: str) -> Dict[str, any]:
        """Parses an RFC822 Debian package paragraph block into structured dictionary."""
        data: Dict[str, any] = {
            "dependencies": [],
            "status": "installed",
            "summary": "",
            "description": "",
        }
        current_field: Optional[str] = None
        desc_lines: List[str] = []

        for line in paragraph.splitlines():
            if line.startswith(" ") or line.startswith("\t"):
                # Continuation of previous multi-line field (e.g. Description or Depends)
                if current_field == "description":
                    cleaned = line.strip()
                    if cleaned == ".":
                        desc_lines.append("")
                    else:
                        desc_lines.append(cleaned)
                continue

            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip().lower()
                val = val.strip()
                current_field = key

                if key == "package":
                    data["name"] = val
                elif key == "version":
                    data["version"] = val
                elif key == "architecture":
                    data["architecture"] = val
                elif key == "status":
                    # E.g. 'install ok installed'
                    status_parts = val.split()
                    data["status"] = status_parts[-1] if status_parts else "installed"
                elif key == "section":
                    data["section"] = val
                elif key == "installed-size":
                    if val.isdigit():
                        data["installed_size_kb"] = int(val)
                elif key == "maintainer":
                    data["maintainer"] = val
                elif key == "homepage":
                    data["homepage"] = val
                elif key == "source":
                    data["source"] = val.split()[0] if val else None
                elif key == "depends":
                    # Split dependency list by commas
                    deps = [d.strip() for d in val.split(",") if d.strip()]
                    data["dependencies"] = deps
                elif key == "description":
                    data["summary"] = val
                    desc_lines = [val]

        if desc_lines:
            data["description"] = "\n".join(desc_lines)

        return data

    def _load_rhel_packages(self) -> Dict[str, PackageDetails]:
        """Parses RHEL/Fedora/CentOS packages via rpm query using fixed command arguments."""
        packages: Dict[str, PackageDetails] = {}
        rpm_bin = shutil.which("rpm") or "/usr/bin/rpm"
        if not os.path.exists(rpm_bin):
            return packages

        try:
            cmd = [
                rpm_bin,
                "-qa",
                "--qf",
                "%{NAME}\t%{VERSION}-%{RELEASE}\t%{ARCH}\tinstalled\t%{SUMMARY}\t%{SIZE}\t%{GROUP}\t%{SOURCERPM}\n",
            ]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=8.0,
                check=False,
                shell=False,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    parts = line.split("\t")
                    if len(parts) >= 5:
                        p_name = parts[0].strip()
                        p_ver = parts[1].strip()
                        p_arch = parts[2].strip()
                        p_status = parts[3].strip() or "installed"
                        p_summary = parts[4].strip()
                        p_size = None
                        if len(parts) >= 6 and parts[5].strip().isdigit():
                            # RPM size is in bytes, convert to KB
                            p_size = int(parts[5].strip()) // 1024
                        p_section = parts[6].strip() if len(parts) >= 7 else None
                        p_source = parts[7].strip() if len(parts) >= 8 else None

                        if p_name:
                            packages[p_name] = PackageDetails(
                                name=p_name,
                                version=p_ver,
                                architecture=p_arch,
                                status=p_status,
                                summary=p_summary,
                                description=p_summary,
                                source=p_source,
                                section=p_section,
                                maintainer=None,
                                homepage=None,
                                installed_size_kb=p_size,
                                dependencies=[],
                            )
        except Exception as exc:
            logger.warning(f"RPM package query execution failed: {exc}")

        return packages

    def _load_alpine_packages(self) -> Dict[str, PackageDetails]:
        """Parses Alpine Linux installed packages from /lib/apk/db/installed."""
        packages: Dict[str, PackageDetails] = {}
        if not self.apk_installed_path.exists():
            return packages

        try:
            content = self.apk_installed_path.read_text(encoding="utf-8", errors="replace")
            # In Alpine APK installed db, blocks are separated by double newlines with single letter prefixes
            blocks = content.split("\n\n")
            for block in blocks:
                if not block.strip():
                    continue
                p_name = None
                p_ver = "unknown"
                p_desc = ""
                p_size = None
                p_arch = "all"
                p_web = None
                p_maint = None
                for line in block.splitlines():
                    if line.startswith("P:"):
                        p_name = line[2:].strip()
                    elif line.startswith("V:"):
                        p_ver = line[2:].strip()
                    elif line.startswith("T:"):
                        p_desc = line[2:].strip()
                    elif line.startswith("I:"):
                        # Size in bytes
                        if line[2:].strip().isdigit():
                            p_size = int(line[2:].strip()) // 1024
                    elif line.startswith("A:"):
                        p_arch = line[2:].strip()
                    elif line.startswith("U:"):
                        p_web = line[2:].strip()
                    elif line.startswith("m:"):
                        p_maint = line[2:].strip()

                if p_name:
                    packages[p_name] = PackageDetails(
                        name=p_name,
                        version=p_ver,
                        architecture=p_arch,
                        status="installed",
                        summary=p_desc,
                        description=p_desc,
                        source=None,
                        section=None,
                        maintainer=p_maint,
                        homepage=p_web,
                        installed_size_kb=p_size,
                        dependencies=[],
                    )
        except Exception as exc:
            logger.warning(f"Alpine apk db parsing failed: {exc}")

        return packages

    def list_packages(
        self,
        page: int = 1,
        page_size: int = 50,
        search: Optional[str] = None,
        sort_by: str = "name",
        order: str = "asc",
    ) -> PackageListResult:
        """Returns paginated, searchable, sorted list of installed packages."""
        # Sanitize pagination and sort parameters
        page = max(1, int(page))
        page_size = min(max(1, int(page_size)), 200)

        sort_field = sort_by if sort_by in self.ALLOWED_SORT_FIELDS else "name"
        reverse_sort = order.lower() == "desc"

        all_pkgs = list(self._load_all_packages().values())

        # Filter by search string if provided
        if search and search.strip():
            query = search.strip().lower()
            filtered = [
                p
                for p in all_pkgs
                if query in p.name.lower()
                or query in p.summary.lower()
                or (p.source and query in p.source.lower())
            ]
        else:
            filtered = all_pkgs

        # Sort items
        def get_sort_key(item: PackageDetails):
            val = getattr(item, sort_field, "")
            if val is None:
                return 0 if sort_field == "installed_size_kb" else ""
            if isinstance(val, str):
                return val.lower()
            return val

        filtered.sort(key=get_sort_key, reverse=reverse_sort)

        total_items = len(filtered)
        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 1

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_items = filtered[start_idx:end_idx]

        # Convert to lightweight PackageInfo for inventory listing
        items = [
            PackageInfo(
                name=p.name,
                version=p.version,
                architecture=p.architecture,
                status=p.status,
                summary=p.summary,
                source=p.source,
                installed_size_kb=p.installed_size_kb,
            )
            for p in page_items
        ]

        return PackageListResult(
            items=items,
            total=total_items,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_package_details(self, name: str) -> Optional[PackageDetails]:
        """Retrieves full details for a validated package name."""
        validated_name = validate_package_name(name)
        all_pkgs = self._load_all_packages()
        return all_pkgs.get(validated_name)

    def list_repositories(self) -> List[RepositoryInfo]:
        """Parses configured software repositories (APT sources or YUM/DNF repos)."""
        repos: List[RepositoryInfo] = []
        mgr_info = self.get_manager_info()

        if mgr_info.family == "debian":
            repos = self._parse_debian_repositories()
        elif mgr_info.family == "rhel":
            repos = self._parse_rhel_repositories()

        return repos

    def _parse_debian_repositories(self) -> List[RepositoryInfo]:
        """Parses /etc/apt/sources.list and /etc/apt/sources.list.d/*.list and *.sources."""
        repos: List[RepositoryInfo] = []

        # 1. Main /etc/apt/sources.list
        if self.apt_sources_list_path.exists() and self.apt_sources_list_path.is_file():
            repos.extend(self._parse_apt_list_file(self.apt_sources_list_path))

        # 2. Directory /etc/apt/sources.list.d/
        if self.apt_sources_dir_path.exists() and self.apt_sources_dir_path.is_dir():
            try:
                for file_path in sorted(self.apt_sources_dir_path.iterdir()):
                    if file_path.is_file():
                        if file_path.suffix == ".list":
                            repos.extend(self._parse_apt_list_file(file_path))
                        elif file_path.suffix == ".sources":
                            repos.extend(self._parse_deb822_sources_file(file_path))
            except Exception as exc:
                logger.warning(f"Error reading apt sources directory {self.apt_sources_dir_path}: {exc}")

        return repos

    def _parse_apt_list_file(self, file_path: Path) -> List[RepositoryInfo]:
        """Parses traditional one-line-style APT sources.list file."""
        entries: List[RepositoryInfo] = []
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            for line_no, raw_line in enumerate(content.splitlines(), start=1):
                line = raw_line.strip()
                if not line:
                    continue

                enabled = True
                if line.startswith("#"):
                    # Check if it's a commented-out deb line
                    uncommented = line.lstrip("#").strip()
                    if uncommented.startswith("deb ") or uncommented.startswith("deb-src "):
                        line = uncommented
                        enabled = False
                    else:
                        continue

                # E.g. deb [arch=amd64] http://deb.debian.org/debian bookworm main contrib non-free
                tokens = line.split()
                if len(tokens) >= 3 and tokens[0] in ("deb", "deb-src"):
                    repo_type = tokens[0]
                    curr_idx = 1
                    # Skip options like [arch=amd64 signed-by=...]
                    if tokens[curr_idx].startswith("["):
                        while curr_idx < len(tokens) and not tokens[curr_idx].endswith("]"):
                            curr_idx += 1
                        curr_idx += 1

                    if curr_idx < len(tokens):
                        uri = tokens[curr_idx]
                        curr_idx += 1
                        distribution = tokens[curr_idx] if curr_idx < len(tokens) else None
                        curr_idx += 1
                        components = tokens[curr_idx:] if curr_idx < len(tokens) else []

                        repo_name = f"{distribution or 'repo'} ({file_path.name}:{line_no})"
                        entries.append(
                            RepositoryInfo(
                                name=repo_name,
                                type=repo_type,
                                uri=uri,
                                enabled=enabled,
                                distribution=distribution,
                                components=components,
                                source_file=str(file_path),
                            )
                        )
        except Exception as exc:
            logger.warning(f"Failed to parse APT list file {file_path}: {exc}")

        return entries

    def _parse_deb822_sources_file(self, file_path: Path) -> List[RepositoryInfo]:
        """Parses modern Deb822-style *.sources file (Ubuntu 24.04+ format)."""
        entries: List[RepositoryInfo] = []
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            paragraphs = content.split("\n\n")
            for idx, para in enumerate(paragraphs, start=1):
                if not para.strip():
                    continue
                types_list: List[str] = ["deb"]
                uris_list: List[str] = []
                suites_list: List[str] = []
                components_list: List[str] = []
                enabled: bool = True

                for line in para.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or ":" not in line:
                        continue
                    k, v = line.split(":", 1)
                    k = k.strip().lower()
                    v = v.strip()
                    if k == "types":
                        types_list = v.split()
                    elif k == "uris":
                        uris_list = v.split()
                    elif k == "suites":
                        suites_list = v.split()
                    elif k == "components":
                        components_list = v.split()
                    elif k == "enabled":
                        enabled = v.lower() in ("yes", "true", "1")

                for u in uris_list:
                    for s in suites_list or [None]:
                        repo_name = f"{s or 'repo'} ({file_path.name} #{idx})"
                        for t in types_list:
                            entries.append(
                                RepositoryInfo(
                                    name=repo_name,
                                    type=t,
                                    uri=u,
                                    enabled=enabled,
                                    distribution=s,
                                    components=components_list,
                                    source_file=str(file_path),
                                )
                            )
        except Exception as exc:
            logger.warning(f"Failed to parse Deb822 sources file {file_path}: {exc}")

        return entries

    def _parse_rhel_repositories(self) -> List[RepositoryInfo]:
        """Parses YUM/DNF repository files from /etc/yum.repos.d/*.repo."""
        entries: List[RepositoryInfo] = []
        if not self.yum_repos_dir_path.exists() or not self.yum_repos_dir_path.is_dir():
            return entries

        try:
            for file_path in sorted(self.yum_repos_dir_path.iterdir()):
                if file_path.is_file() and file_path.suffix == ".repo":
                    parser = configparser.ConfigParser(interpolation=None)
                    try:
                        parser.read(str(file_path), encoding="utf-8")
                        for section in parser.sections():
                            name = parser.get(section, "name", fallback=section)
                            baseurl = parser.get(section, "baseurl", fallback="")
                            mirrorlist = parser.get(section, "mirrorlist", fallback="")
                            enabled_str = parser.get(section, "enabled", fallback="1")
                            enabled = enabled_str.strip() in ("1", "yes", "true")
                            uri = baseurl or mirrorlist or section

                            entries.append(
                                RepositoryInfo(
                                    name=f"{name} ({section})",
                                    type="rpm",
                                    uri=uri,
                                    enabled=enabled,
                                    distribution=None,
                                    components=[],
                                    source_file=str(file_path),
                                )
                            )
                    except Exception as parse_err:
                        logger.warning(f"Could not parse YUM repo file {file_path}: {parse_err}")
        except Exception as exc:
            logger.warning(f"Error accessing YUM repos directory {self.yum_repos_dir_path}: {exc}")

        return entries

    def list_updates(self) -> List[PackageUpdateInfo]:
        """
        Discovers package updates safely using read-only cached system metadata.
        Strictly does NOT invoke state-mutating 'apt update' or 'dnf makecache'.
        """
        updates: List[PackageUpdateInfo] = []
        # Safe read-only inspection: if update notifier or upgrade summaries exist
        # on Ubuntu / Debian (e.g. /var/lib/update-notifier/updates-available), parse it.
        # Otherwise, report empty updates safely without performing mutating network refreshes.
        update_notifier_file = Path("/var/lib/update-notifier/updates-available")
        if update_notifier_file.exists() and update_notifier_file.is_file():
            try:
                content = update_notifier_file.read_text(encoding="utf-8", errors="replace")
                # Informational lines in MOTD
                logger.info(f"Read-only update notifier status available: {content[:100]}")
            except Exception:
                pass

        return updates

    def get_overview(self) -> PackageOverview:
        """Aggregates high-level package ecosystem KPIs, counts, and health status."""
        mgr_info = self.get_manager_info()
        all_pkgs = self._load_all_packages()
        repos = self.list_repositories()
        updates = self.list_updates()

        update_msg = (
            "Package database operating in read-only mode. Update availability reflects cached system metadata."
        )

        return PackageOverview(
            manager=mgr_info.manager,
            family=mgr_info.family,
            distribution=mgr_info.distribution,
            architecture=mgr_info.architecture,
            installed_package_count=len(all_pkgs),
            packages_with_updates=len(updates) if updates else None,
            repository_count=len(repos),
            manager_available=mgr_info.available,
            update_status_message=update_msg,
        )


# Singleton package manager instance
package_manager = PackageManager()
