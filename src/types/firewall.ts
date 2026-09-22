export interface FirewallRule {
  rule_index: number;
  port: string;
  protocol: string;
  action: 'ALLOW' | 'DENY' | string;
  direction: 'IN' | 'OUT' | string;
  source: string;
  family: 'ipv4' | 'ipv6' | string;
  comment?: string | null;
  signature?: string | null;
}

export interface FirewallStatus {
  installed: boolean;
  active: boolean;
  default_incoming: string;
  default_outgoing: string;
  default_routed: string;
  rules: FirewallRule[];
  management_ports: number[];
}

export interface FirewallRuleCreateInput {
  port: string;
  protocol: 'tcp' | 'udp' | 'any';
  action: 'allow' | 'deny';
  direction: 'in' | 'out';
  source_ip: string;
  comment?: string;
}

export interface FirewallToggleInput {
  enable: boolean;
}
