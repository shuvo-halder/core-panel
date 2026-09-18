export interface PackageManagerInfo {
  manager: string;
  family: string;
  distribution: string;
  version: string;
  architecture: string;
  available: boolean;
}

export interface PackageItem {
  name: string;
  version: string;
  architecture: string;
  status: string;
  summary: string;
  source?: string | null;
  installed_size_kb?: number | null;
}

export interface PackageDetails {
  name: string;
  version: string;
  architecture: string;
  status: string;
  summary: string;
  description: string;
  source?: string | null;
  section?: string | null;
  maintainer?: string | null;
  homepage?: string | null;
  installed_size_kb?: number | null;
  dependencies: string[];
}

export interface PackageListResponse {
  items: PackageItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface RepositoryInfo {
  name: string;
  type: string;
  uri: string;
  enabled: boolean;
  distribution?: string | null;
  components: string[];
  source_file?: string | null;
}

export interface PackageUpdateInfo {
  name: string;
  installed_version: string;
  candidate_version: string;
  repository?: string | null;
  update_available: boolean;
  urgency?: string | null;
}

export interface PackageOverview {
  manager: string;
  family: string;
  distribution: string;
  architecture: string;
  installed_package_count: number;
  packages_with_updates?: number | null;
  repository_count: number;
  manager_available: boolean;
  update_status_message?: string | null;
}
