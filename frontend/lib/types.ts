export interface ConnectionEvent {
  event_id: string;
  timestamp: string;
  process_name: string;
  pid: number;
  src_ip: string;
  src_port: number;
  dst_ip: string;
  dst_hostname: string | null;
  dst_country: string | null;
  dst_asn: string | null;
  dst_org: string | null;
  dst_port: number;
  protocol: string;
  bytes_sent: number;
  bytes_recv: number;
  state: string;
  threat_intel: { is_blocklisted: boolean; source: string | null };
  severity: string;
}

export interface AlertEvent {
  alert_id: string;
  timestamp: string;
  severity: string;
  rule_id: string;
  reason: string;
  confidence: number;
  process_name: string;
  pid: number;
  dst_ip: string;
  dst_hostname: string | null;
  recommended_action: string;
  suppressed: boolean;
}

export interface ThreatEvent {
  threat_id: string;
  detected_at: string;
  severity: string;
  threat_type: string;
  process_name: string;
  pid: number;
  dst_ip: string;
  dst_hostname: string | null;
  reason: string;
  confidence: number;
  status: string;
  remediation_status: string | null;
  killed_at: string | null;
  block_ip_at: string | null;
}

export interface AllowlistRule {
  rule_id: string;
  process_name: string | null;
  dst_ip: string | null;
  dst_hostname: string | null;
  expires_at: string | null;
  reason: string | null;
  created_at: string;
}

export interface Suppression {
  suppression_id: string;
  rule_id: string | null;
  process_name: string | null;
  scope: string;
  reason: string | null;
  alert_id: string | null;
  created_at: string;
}

export interface StatsSummary {
  total_connections: number;
  unique_destinations: number;
  active_alerts: number;
  top_processes: { process_name: string; count: number }[];
  top_destinations: { dst_ip: string; count: number }[];
}

export interface CaptureStatus {
  capture: 'running' | 'stopped';
  interface: string;
  uptime: number;
  probe_type: string;
}

export interface Pagination {
  page: number;
  page_size: number;
  total: number;
}

export const SEVERITY_CLASSES: Record<string, string> = {
  INFO:     'text-info',
  LOW:      'text-secondary',
  WARNING:  'text-warning',
  ALERT:    'text-pnpg-alert',
  HIGH:     'text-pnpg-alert',
  CRITICAL: 'text-danger',
  THREAT:   'text-danger',
};

export const SEVERITY_BADGE: Record<string, string> = {
  INFO:     'bg-info bg-opacity-25 text-info',
  LOW:      'bg-secondary',
  WARNING:  'bg-warning text-dark',
  ALERT:    'bg-pnpg-alert text-dark',
  HIGH:     'bg-pnpg-alert text-dark',
  CRITICAL: 'bg-danger',
  THREAT:   'bg-danger',
};
