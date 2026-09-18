export interface ProcessSummary {
  pid: number;
  ppid: number;
  name: string;
  username: string | null;
  uid: number;
  state: string;
  cpu_percent: number;
  memory_rss_bytes: number;
  memory_vsz_bytes: number;
  memory_percent: number;
  start_time: string;
  start_time_ticks: number;
  threads: number;
  command_summary: string | null;
  is_protected: boolean;
}

export interface ProcessListResponse {
  items: ProcessSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ProcessMutationResult {
  success: boolean;
  pid: number;
  operation: string;
  signal: string;
  status: string;
  message: string;
}
