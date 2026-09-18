export interface ServiceSummary {
  unit: string;
  description: string;
  load_state: string;
  active_state: string;
  sub_state: string;
  enabled: string;
  main_pid: number | null;
}

export interface ServiceMutationResult {
  success: boolean;
  operation: string;
  unit: string;
  message: string;
  service?: ServiceSummary | null;
}
