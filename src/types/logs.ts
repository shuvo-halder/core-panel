export type LogSeverityLevel =
  | 'EMERG'
  | 'ALERT'
  | 'CRIT'
  | 'ERR'
  | 'WARNING'
  | 'NOTICE'
  | 'INFO'
  | 'DEBUG';

export interface LogSource {
  id: string;
  name: string;
  source_type: 'JOURNAL' | 'FILE';
  path: string | null;
  available: boolean;
  size_bytes: number | null;
  last_modified: string | null;
  description: string | null;
}

export interface LogOverview {
  available_sources: LogSource[];
  journal_available: boolean;
  total_sources_count: number;
  active_sources_count: number;
  severity_counts: Record<string, number>;
  latest_timestamp: string | null;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  source: string;
  hostname: string | null;
  service: string | null;
  unit: string | null;
  severity: LogSeverityLevel | string;
  facility: string | null;
  message: string;
  pid: number | null;
  uid: number | null;
  boot_id: string | null;
  metadata: Record<string, unknown> | null;
}

export interface LogPage {
  items: LogEntry[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  source: string | null;
}

export interface AuditLogEntry {
  id: string;
  user_id: string | null;
  username: string;
  action: string;
  resource_type: string;
  resource_id: string;
  status: string;
  details: string | null;
  ip_address: string | null;
  request_id: string | null;
  created_at: string;
}

export interface AuditLogPage {
  items: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface LogQueryParams {
  source?: string;
  severity?: string;
  service?: string;
  unit?: string;
  search?: string;
  since?: string;
  until?: string;
  page?: number;
  page_size?: number;
}

export interface AuditQueryParams {
  user_id?: string;
  username?: string;
  action?: string;
  resource_type?: string;
  status?: string;
  search?: string;
  since?: string;
  until?: string;
  page?: number;
  page_size?: number;
}
