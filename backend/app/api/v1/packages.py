from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.app.auth.dependencies import require_permission
from backend.app.auth.models import UserRead
from backend.app.core.errors import NotFoundError
from backend.app.core.validators import validate_package_name
from backend.app.linux.packages import package_manager

router = APIRouter(prefix="/packages", tags=["Package Management"])


class PackageItemResponse(BaseModel):
    name: str
    version: str
    architecture: str
    status: str
    summary: str
    source: Optional[str] = None
    installed_size_kb: Optional[int] = None


class PackageDetailsResponse(BaseModel):
    name: str
    version: str
    architecture: str
    status: str
    summary: str
    description: str
    source: Optional[str] = None
    section: Optional[str] = None
    maintainer: Optional[str] = None
    homepage: Optional[str] = None
    installed_size_kb: Optional[int] = None
    dependencies: List[str] = []


class PackageListResponse(BaseModel):
    items: List[PackageItemResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class RepositoryResponse(BaseModel):
    name: str
    type: str
    uri: str
    enabled: bool
    distribution: Optional[str] = None
    components: List[str] = []
    source_file: Optional[str] = None


class PackageUpdateResponse(BaseModel):
    name: str
    installed_version: str
    candidate_version: str
    repository: Optional[str] = None
    update_available: bool = True
    urgency: Optional[str] = None


class PackageOverviewResponse(BaseModel):
    manager: str
    family: str
    distribution: str
    architecture: str
    installed_package_count: int
    packages_with_updates: Optional[int] = None
    repository_count: int = 0
    manager_available: bool = True
    update_status_message: Optional[str] = None


@router.get(
    "/overview",
    response_model=PackageOverviewResponse,
    summary="Get package ecosystem overview",
    description="Retrieves summary KPIs, active package manager, distribution, and repository counts.",
)
async def get_package_overview(
    _current_user: UserRead = Depends(require_permission("packages.read")),
) -> PackageOverviewResponse:
    overview = package_manager.get_overview()
    return PackageOverviewResponse(
        manager=overview.manager,
        family=overview.family,
        distribution=overview.distribution,
        architecture=overview.architecture,
        installed_package_count=overview.installed_package_count,
        packages_with_updates=overview.packages_with_updates,
        repository_count=overview.repository_count,
        manager_available=overview.manager_available,
        update_status_message=overview.update_status_message,
    )


@router.get(
    "",
    response_model=PackageListResponse,
    summary="List installed packages",
    description="Returns a paginated, searchable, sorted inventory of installed operating system packages.",
)
async def get_packages(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page (max 200)"),
    search: Optional[str] = Query(None, description="Search term for package name, summary, or source"),
    sort: str = Query("name", description="Sort field (name, version, status, installed_size_kb, architecture)"),
    order: str = Query("asc", description="Sort direction (asc or desc)"),
    _current_user: UserRead = Depends(require_permission("packages.read")),
) -> PackageListResponse:
    res = package_manager.list_packages(
        page=page,
        page_size=page_size,
        search=search,
        sort_by=sort,
        order=order,
    )
    return PackageListResponse(
        items=[
            PackageItemResponse(
                name=p.name,
                version=p.version,
                architecture=p.architecture,
                status=p.status,
                summary=p.summary,
                source=p.source,
                installed_size_kb=p.installed_size_kb,
            )
            for p in res.items
        ],
        total=res.total,
        page=res.page,
        page_size=res.page_size,
        total_pages=res.total_pages,
    )


@router.get(
    "/repositories",
    response_model=List[RepositoryResponse],
    summary="List configured package repositories",
    description="Retrieves read-only repository sources and component configurations.",
)
async def get_repositories(
    _current_user: UserRead = Depends(require_permission("packages.read")),
) -> List[RepositoryResponse]:
    repos = package_manager.list_repositories()
    return [
        RepositoryResponse(
            name=r.name,
            type=r.type,
            uri=r.uri,
            enabled=r.enabled,
            distribution=r.distribution,
            components=r.components,
            source_file=r.source_file,
        )
        for r in repos
    ]


@router.get(
    "/updates",
    response_model=List[PackageUpdateResponse],
    summary="List available package updates",
    description="Retrieves available package updates safely using non-mutating cached system metadata.",
)
async def get_package_updates(
    _current_user: UserRead = Depends(require_permission("packages.read")),
) -> List[PackageUpdateResponse]:
    updates = package_manager.list_updates()
    return [
        PackageUpdateResponse(
            name=u.name,
            installed_version=u.installed_version,
            candidate_version=u.candidate_version,
            repository=u.repository,
            update_available=u.update_available,
            urgency=u.urgency,
        )
        for u in updates
    ]


@router.get(
    "/{name}",
    response_model=PackageDetailsResponse,
    summary="Get package details",
    description="Retrieves full metadata, description, maintainer, and dependencies for a validated package name.",
)
async def get_package_by_name(
    name: str,
    _current_user: UserRead = Depends(require_permission("packages.read")),
) -> PackageDetailsResponse:
    validated_name = validate_package_name(name)
    pkg = package_manager.get_package_details(validated_name)
    if not pkg:
        raise NotFoundError(
            f"Package '{validated_name}' not found",
            code="PACKAGE_NOT_FOUND",
        )

    return PackageDetailsResponse(
        name=pkg.name,
        version=pkg.version,
        architecture=pkg.architecture,
        status=pkg.status,
        summary=pkg.summary,
        description=pkg.description,
        source=pkg.source,
        section=pkg.section,
        maintainer=pkg.maintainer,
        homepage=pkg.homepage,
        installed_size_kb=pkg.installed_size_kb,
        dependencies=pkg.dependencies,
    )
