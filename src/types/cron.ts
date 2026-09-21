export type CronSource =
  | 'USER_CRONTAB'
  | 'SYSTEM_CRONTAB'
  | 'CRON_D_DIRECTORY'
  | 'PERIODIC_DIRECTORY';

export interface CronJob {
  id: string;
  owner: string;
  schedule: string;
  minute: string;
  hour: string;
  day_of_month: string;
  month: string;
  day_of_week: string;
  special_expression?: string | null;
  command: string;
  comment?: string | null;
  enabled: boolean;
  source: CronSource | string;
  source_file?: string | null;
  line_number?: number | null;
  description?: string | null;
  is_editable: boolean;
  original_hash?: string | null;
}

export interface CronListResponse {
  items: CronJob[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface CronOverview {
  total_jobs: number;
  active_jobs: number;
  disabled_jobs: number;
  users_with_crontabs: number;
  user_jobs_count: number;
  system_jobs_count: number;
  cron_d_jobs_count: number;
  periodic_jobs_count: number;
  available_sources: string[];
}

export interface CronEligibleUser {
  username: string;
  uid: number;
  gid: number;
  home: string;
  shell: string;
}

export interface CronJobCreateRequest {
  owner: string;
  schedule: string;
  command: string;
  comment?: string | null;
  enabled: boolean;
}

export interface CronJobUpdateRequest {
  owner: string;
  schedule: string;
  command: string;
  comment?: string | null;
  enabled: boolean;
  expected_hash?: string | null;
}

export interface CronJobMutationResult {
  success: boolean;
  operation: string;
  job: CronJob;
  message: string;
}

export interface CronJobDeleteResult {
  success: boolean;
  operation: string;
  deleted_id: string;
  owner: string;
  message: string;
}
