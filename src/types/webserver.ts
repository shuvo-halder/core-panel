export interface NginxOverview {
  installed: boolean;
  version?: string | null;
  executable_path?: string | null;
  service_active: boolean;
  config_path?: string | null;
  sites_available_count: number;
  sites_enabled_count: number;
  config_valid: boolean;
  config_error?: string | null;
}

export interface SiteProxy {
  enabled: boolean;
  target?: string | null;
  preserve_host: boolean;
}

export interface SiteSSL {
  enabled: boolean;
  certificate?: string | null;
  cert_exists: boolean;
  subject?: string | null;
  issuer?: string | null;
  not_after?: string | null;
  days_remaining?: number | null;
}

export interface SiteConfig {
  name: string;
  server_names: string[];
  listen: number;
  listen_ipv6: boolean;
  root?: string | null;
  proxy: SiteProxy;
  ssl: SiteSSL;
  access_log: boolean;
  error_log: boolean;
  index: string[];
  client_max_body_size: string;
  enabled: boolean;
  managed: boolean;
  config_path?: string | null;
}

export interface SiteCreateInput {
  name: string;
  server_names: string[];
  listen: number;
  listen_ipv6: boolean;
  root?: string | null;
  proxy_enabled: boolean;
  proxy_target?: string | null;
  proxy_preserve_host: boolean;
  ssl_enabled: boolean;
  ssl_certificate?: string | null;
  ssl_certificate_key?: string | null;
  access_log: boolean;
  error_log: boolean;
  index: string[];
  client_max_body_size: string;
  enabled: boolean;
}

export interface SiteUpdateInput {
  server_names: string[];
  listen: number;
  listen_ipv6: boolean;
  root?: string | null;
  proxy_enabled: boolean;
  proxy_target?: string | null;
  proxy_preserve_host: boolean;
  ssl_enabled: boolean;
  ssl_certificate?: string | null;
  ssl_certificate_key?: string | null;
  access_log: boolean;
  error_log: boolean;
  index: string[];
  client_max_body_size: string;
  enabled: boolean;
}

export interface ConfigValidationResult {
  valid: boolean;
  output?: string | null;
  error?: string | null;
}

export interface ReloadResult {
  success: boolean;
  message?: string | null;
  error?: string | null;
}
