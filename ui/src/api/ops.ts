/**
 * Operations API client
 * 
 * Provides access to operational data and management endpoints from Phase 10.
 * All requests automatically include tenant context via httpClient interceptors.
 */

import { httpClient } from '../utils/httpClient'

// ============================================================================
// Types
// ============================================================================

export interface DLQEntry {
  eventId: string
  eventType: string
  tenantId: string
  exceptionId?: string | null
  originalTopic: string
  failureReason: string
  retryCount: number
  workerType: string
  payload: Record<string, unknown>
  eventMetadata: Record<string, unknown>
  failedAt: string
  status?: 'pending' | 'retrying' | 'discarded' | 'succeeded'
}

export interface DLQListResponse {
  items: DLQEntry[]
  total: number
  limit: number
  offset: number
}

export interface WorkerHealth {
  workerType: string
  instanceId: string
  status: 'healthy' | 'degraded' | 'unhealthy'
  lastCheck: string
  responseTime?: number
  version?: string
  host?: string
}

export interface WorkerHealthResponse {
  workers: WorkerHealth[]
}

export interface WorkerThroughput {
  workerType: string
  eventsPerSecond: number
  latencyP50?: number
  latencyP95?: number
  latencyP99?: number
  errorRate?: number
}

export interface WorkerThroughputResponse {
  throughput: WorkerThroughput[]
}

export interface SLACompliance {
  tenantId: string
  complianceRate: number
  period: string
}

export interface SLABreach {
  exceptionId: string
  tenantId: string
  domain: string
  exceptionType: string
  severity: string
  breachTimestamp: string
  slaDeadline: string
}

export interface SLAAtRisk {
  exceptionId: string
  tenantId: string
  domain: string
  exceptionType: string
  severity: string
  timeUntilDeadline: string
}

export interface SLAComplianceResponse {
  complianceRate: number
  period: string
}

export interface SLABreachesResponse {
  breaches: SLABreach[]
  total: number
}

export interface SLAAtRiskResponse {
  atRisk: SLAAtRisk[]
  total: number
}

export interface AlertConfig {
  id?: string
  alertType: 'SLA_BREACH' | 'SLA_IMMINENT' | 'DLQ_GROWTH' | 'WORKER_UNHEALTHY' | 'ERROR_RATE_HIGH' | 'THROUGHPUT_LOW'
  name: string
  enabled: boolean
  thresholdValue?: number
  thresholdUnit?: string
  severity?: string
  channels?: string[]
  createdAt?: string
  updatedAt?: string
}

export interface AlertChannel {
  id: string
  tenantId: string
  channelType: 'webhook' | 'email'
  config: Record<string, unknown>
  verified: boolean
  createdAt?: string
}

export interface AlertHistory {
  id: string
  alertId: string
  alertType: string
  severity: string
  status: 'fired' | 'acknowledged' | 'resolved'
  triggeredAt: string
  acknowledgedAt?: string
  resolvedAt?: string
  tenantId: string
  domain?: string
  payload?: Record<string, unknown>
  notificationStatus?: string
}

export interface AlertHistoryResponse {
  items: AlertHistory[]
  total: number
}

export interface AuditReport {
  id: string
  tenantId: string
  reportType: 'exception_activity' | 'tool_execution' | 'policy_decisions' | 'config_changes' | 'sla_compliance'
  status: 'queued' | 'generating' | 'completed' | 'failed'
  requestedBy: string
  requestedAt: string
  completedAt?: string
  downloadUrl?: string
  expiresAt?: string
  errorReason?: string
  parameters?: Record<string, unknown>
}

export interface AuditReportRequest {
  reportType: string
  tenantId?: string
  domain?: string
  dateFrom?: string
  dateTo?: string
  format?: 'csv' | 'json'
}

export interface AuditReportResponse {
  reportId: string
  status: string
}

export interface UsageSummary {
  tenantId: string
  resourceType: string
  count: number
  period: string
}

export interface UsageSummaryResponse {
  summary: UsageSummary[]
  period: string
}

// ============================================================================
// DLQ API
// ============================================================================

export interface ListDLQParams {
  tenantId: string
  status?: string
  eventType?: string
  limit?: number
  offset?: number
}

export async function listDLQEntries(params: ListDLQParams): Promise<DLQListResponse> {
  const response = await httpClient.get<{
    items: any[]
    total: number
    limit: number
    offset: number
  }>('/ops/dlq', {
    params: {
      tenant_id: params.tenantId,
      status: params.status,
      event_type: params.eventType,
      limit: params.limit || 100,
      offset: params.offset || 0,
    },
  })

  const items: DLQEntry[] = (response.items || []).map((item: any) => ({
    eventId: item.event_id || item.eventId || '',
    eventType: item.event_type || item.eventType || '',
    tenantId: item.tenant_id || item.tenantId || params.tenantId,
    exceptionId: item.exception_id || item.exceptionId || null,
    originalTopic: item.original_topic || item.originalTopic || '',
    failureReason: item.failure_reason || item.failureReason || '',
    retryCount: item.retry_count || item.retryCount || 0,
    workerType: item.worker_type || item.workerType || '',
    payload: item.payload || {},
    eventMetadata: item.event_metadata || item.eventMetadata || {},
    failedAt: item.failed_at || item.failedAt || '',
    status: item.status || 'pending',
  }))

  return {
    items,
    total: response.total || 0,
    limit: response.limit || 100,
    offset: response.offset || 0,
  }
}

export async function getDLQEntry(id: string, tenantId: string): Promise<DLQEntry> {
  const response = await httpClient.get<any>(`/ops/dlq/${id}`, {
    params: { tenant_id: tenantId },
  })

  return {
    eventId: response.event_id || response.eventId || id,
    eventType: response.event_type || response.eventType || '',
    tenantId: response.tenant_id || response.tenantId || tenantId,
    exceptionId: response.exception_id || response.exceptionId || null,
    originalTopic: response.original_topic || response.originalTopic || '',
    failureReason: response.failure_reason || response.failureReason || '',
    retryCount: response.retry_count || response.retryCount || 0,
    workerType: response.worker_type || response.workerType || '',
    payload: response.payload || {},
    eventMetadata: response.event_metadata || response.eventMetadata || {},
    failedAt: response.failed_at || response.failedAt || '',
    status: response.status || 'pending',
  }
}

export async function retryDLQEntry(id: string, tenantId: string): Promise<void> {
  await httpClient.post(`/ops/dlq/${id}/retry`, {}, {
    params: { tenant_id: tenantId },
  })
}

export async function retryDLQBatch(ids: string[], tenantId: string): Promise<void> {
  await httpClient.post('/ops/dlq/retry-batch', { ids }, {
    params: { tenant_id: tenantId },
  })
}

export async function discardDLQEntry(id: string, tenantId: string): Promise<void> {
  await httpClient.post(`/ops/dlq/${id}/discard`, {}, {
    params: { tenant_id: tenantId },
  })
}

// ============================================================================
// Worker Health & Throughput API
// ============================================================================

export async function getWorkerHealth(): Promise<WorkerHealthResponse> {
  const response = await httpClient.get<{ workers: any[] }>('/ops/workers/health')
  
  return {
    workers: (response.workers || []).map((w: any) => ({
      workerType: w.worker_type || w.workerType || '',
      instanceId: w.instance_id || w.instanceId || '',
      status: w.status || 'unhealthy',
      lastCheck: w.last_check || w.lastCheck || '',
      responseTime: w.response_time || w.responseTime,
      version: w.version,
      host: w.host,
    })),
  }
}

export async function getWorkerThroughput(): Promise<WorkerThroughputResponse> {
  const response = await httpClient.get<{ throughput: any[] }>('/ops/workers/throughput')
  
  return {
    throughput: (response.throughput || []).map((t: any) => ({
      workerType: t.worker_type || t.workerType || '',
      eventsPerSecond: t.events_per_second || t.eventsPerSecond || 0,
      latencyP50: t.latency_p50 || t.latencyP50,
      latencyP95: t.latency_p95 || t.latencyP95,
      latencyP99: t.latency_p99 || t.latencyP99,
      errorRate: t.error_rate || t.errorRate,
    })),
  }
}

// ============================================================================
// SLA API
// ============================================================================

export interface GetSLAComplianceParams {
  tenantId?: string
  period?: 'day' | 'week' | 'month'
}

export async function getSLACompliance(params: GetSLAComplianceParams = {}): Promise<SLAComplianceResponse> {
  const response = await httpClient.get<{
    compliance_rate: number
    period: string
  }>('/ops/sla/compliance', {
    params: {
      tenant_id: params.tenantId,
      period: params.period || 'day',
    },
  })

  return {
    complianceRate: response.compliance_rate ?? 0,
    period: response.period || 'day',
  }
}

export interface GetSLABreachesParams {
  tenantId?: string
  domain?: string
  exceptionType?: string
  from?: string
  to?: string
  limit?: number
  offset?: number
}

export async function getSLABreaches(params: GetSLABreachesParams = {}): Promise<SLABreachesResponse> {
  const response = await httpClient.get<{
    breaches: any[]
    total: number
  }>('/ops/sla/breaches', {
    params: {
      tenant_id: params.tenantId,
      domain: params.domain,
      exception_type: params.exceptionType,
      from: params.from,
      to: params.to,
      limit: params.limit || 100,
      offset: params.offset || 0,
    },
  })

  return {
    breaches: (response.breaches || []).map((b: any) => ({
      exceptionId: b.exception_id || b.exceptionId || '',
      tenantId: b.tenant_id || b.tenantId || '',
      domain: b.domain || '',
      exceptionType: b.exception_type || b.exceptionType || '',
      severity: b.severity || '',
      breachTimestamp: b.breach_timestamp || b.breachTimestamp || '',
      slaDeadline: b.sla_deadline || b.slaDeadline || '',
    })),
    total: response.total || 0,
  }
}

export interface GetSLAAtRiskParams {
  tenantId?: string
}

export async function getSLAAtRisk(params: GetSLAAtRiskParams = {}): Promise<SLAAtRiskResponse> {
  const response = await httpClient.get<{
    at_risk: any[]
    total: number
  }>('/ops/sla/at-risk', {
    params: {
      tenant_id: params.tenantId,
    },
  })

  return {
    atRisk: (response.at_risk || []).map((a: any) => ({
      exceptionId: a.exception_id || a.exceptionId || '',
      tenantId: a.tenant_id || a.tenantId || '',
      domain: a.domain || '',
      exceptionType: a.exception_type || a.exceptionType || '',
      severity: a.severity || '',
      timeUntilDeadline: a.time_until_deadline || a.timeUntilDeadline || '',
    })),
    total: response.total || 0,
  }
}

// ============================================================================
// Alerts API
// ============================================================================

export async function listAlertConfigs(tenantId: string): Promise<AlertConfig[]> {
  const response = await httpClient.get<{ items: any[] }>('/alerts/config', {
    params: { tenant_id: tenantId },
  })

  return (response.items || []).map((item: any) => ({
    id: item.id,
    alertType: item.alert_type || item.alertType,
    name: item.name || '',
    enabled: item.enabled !== false,
    thresholdValue: item.threshold_value || item.thresholdValue,
    thresholdUnit: item.threshold_unit || item.thresholdUnit,
    severity: item.severity,
    channels: item.channels || [],
    createdAt: item.created_at || item.createdAt,
    updatedAt: item.updated_at || item.updatedAt,
  }))
}

export async function createAlertConfig(tenantId: string, config: Omit<AlertConfig, 'id' | 'createdAt' | 'updatedAt'>): Promise<AlertConfig> {
  const response = await httpClient.post<AlertConfig>('/alerts/config', config, {
    params: { tenant_id: tenantId },
  })
  return response
}

export async function updateAlertConfig(id: string, tenantId: string, config: Partial<AlertConfig>): Promise<AlertConfig> {
  const response = await httpClient.put<AlertConfig>(`/alerts/config/${id}`, config, {
    params: { tenant_id: tenantId },
  })
  return response
}

export async function deleteAlertConfig(id: string, tenantId: string): Promise<void> {
  await httpClient.delete(`/alerts/config/${id}`, {
    params: { tenant_id: tenantId },
  })
}

export async function listAlertChannels(tenantId: string): Promise<AlertChannel[]> {
  const response = await httpClient.get<{ items: any[] }>('/alerts/channels', {
    params: { tenant_id: tenantId },
  })

  return (response.items || []).map((item: any) => ({
    id: item.id,
    tenantId: item.tenant_id || item.tenantId || tenantId,
    channelType: item.channel_type || item.channelType,
    config: item.config || {},
    verified: item.verified !== false,
    createdAt: item.created_at || item.createdAt,
  }))
}

export async function createAlertChannel(tenantId: string, channel: Omit<AlertChannel, 'id' | 'createdAt'>): Promise<AlertChannel> {
  const response = await httpClient.post<AlertChannel>('/alerts/channels', channel, {
    params: { tenant_id: tenantId },
  })
  return response
}

export async function verifyAlertChannel(id: string, tenantId: string): Promise<void> {
  await httpClient.post(`/alerts/channels/${id}/verify`, {}, {
    params: { tenant_id: tenantId },
  })
}

export async function deleteAlertChannel(id: string, tenantId: string): Promise<void> {
  await httpClient.delete(`/alerts/channels/${id}`, {
    params: { tenant_id: tenantId },
  })
}

export interface GetAlertHistoryParams {
  tenantId: string
  alertType?: string
  status?: string
  severity?: string
  from?: string
  to?: string
  limit?: number
  offset?: number
}

export async function getAlertHistory(params: GetAlertHistoryParams): Promise<AlertHistoryResponse> {
  // Convert offset/limit to page/page_size for backend
  const page = params.offset ? Math.floor(params.offset / (params.limit || 100)) + 1 : 1
  const pageSize = params.limit || 100
  
  const response = await httpClient.get<{
    items: any[]
    total: number
    page: number
    page_size: number
  }>('/alerts/history', {
    params: {
      tenant_id: params.tenantId,
      alert_type: params.alertType,
      status: params.status,
      severity: params.severity,
      from_date: params.from,
      to_date: params.to,
      page: page,
      page_size: pageSize,
    },
  })

  return {
    items: (response.items || []).map((item: any) => ({
      id: item.alert_id || item.id || '',
      alertId: item.alert_id || item.alertId || '',
      alertType: item.alert_type || item.alertType || '',
      severity: item.severity || '',
      status: item.status || 'fired',
      triggeredAt: item.triggered_at || item.triggeredAt || '',
      acknowledgedAt: item.acknowledged_at || item.acknowledgedAt,
      resolvedAt: item.resolved_at || item.resolvedAt,
      tenantId: item.tenant_id || item.tenantId || params.tenantId,
      domain: item.domain,
      payload: item.details || item.payload,
      notificationStatus: item.notification_sent ? 'sent' : 'pending',
    })),
    total: response.total || 0,
  }
}

export async function acknowledgeAlert(id: string, tenantId: string): Promise<void> {
  await httpClient.post(`/alerts/history/${id}/acknowledge`, {}, {
    params: { tenant_id: tenantId },
  })
}

export async function resolveAlert(id: string, tenantId: string): Promise<void> {
  await httpClient.post(`/alerts/history/${id}/resolve`, {}, {
    params: { tenant_id: tenantId },
  })
}

// ============================================================================
// Audit Reports API
// ============================================================================

export async function createAuditReport(tenantId: string, request: AuditReportRequest): Promise<AuditReportResponse> {
  const response = await httpClient.post<AuditReportResponse>('/audit/reports', request, {
    params: { tenant_id: tenantId },
  })
  return response
}

export async function getAuditReport(id: string, tenantId: string): Promise<AuditReport> {
  const response = await httpClient.get<any>(`/audit/reports/${id}`, {
    params: { tenant_id: tenantId },
  })

  return {
    id: response.id,
    tenantId: response.tenant_id || response.tenantId || tenantId,
    reportType: response.report_type || response.reportType,
    status: response.status || 'queued',
    requestedBy: response.requested_by || response.requestedBy || '',
    requestedAt: response.requested_at || response.requestedAt || '',
    completedAt: response.completed_at || response.completedAt,
    downloadUrl: response.download_url || response.downloadUrl,
    expiresAt: response.expires_at || response.expiresAt,
    errorReason: response.error_reason || response.errorReason,
    parameters: response.parameters,
  }
}

export interface ListAuditReportsParams {
  tenantId: string
  status?: string
  limit?: number
  offset?: number
}

export async function listAuditReports(params: ListAuditReportsParams): Promise<{ items: AuditReport[]; total: number }> {
  const response = await httpClient.get<{
    items: any[]
    total: number
  }>('/audit/reports', {
    params: {
      tenant_id: params.tenantId,
      status: params.status,
      limit: params.limit || 100,
      offset: params.offset || 0,
    },
  })

  return {
    items: (response.items || []).map((item: any) => ({
      id: item.id,
      tenantId: item.tenant_id || item.tenantId || params.tenantId,
      reportType: item.report_type || item.reportType,
      status: item.status || 'queued',
      requestedBy: item.requested_by || item.requestedBy || '',
      requestedAt: item.requested_at || item.requestedAt || '',
      completedAt: item.completed_at || item.completedAt,
      downloadUrl: item.download_url || item.downloadUrl,
      expiresAt: item.expires_at || item.expiresAt,
      errorReason: item.error_reason || item.errorReason,
      parameters: item.parameters,
    })),
    total: response.total || 0,
  }
}

// ============================================================================
// Usage Metering API
// ============================================================================

export interface GetUsageSummaryParams {
  tenantId: string
  period?: 'day' | 'week' | 'month'
  fromDate?: string
  toDate?: string
}

export interface UsageSummary {
  resourceType: string
  count: number
  period: string
}

export interface UsageSummaryResponse {
  summary: UsageSummary[]
  period: string
}

export async function getUsageSummary(params: GetUsageSummaryParams): Promise<UsageSummaryResponse> {
  const response = await httpClient.get<{
    tenant_id: string
    period: string
    period_start: string
    period_end: string
    totals: Record<string, number>
    by_resource: Record<string, Record<string, number>>
  }>('/usage/summary', {
    params: {
      tenant_id: params.tenantId,
      period: params.period || 'day',
      from_date: params.fromDate,
      to_date: params.toDate,
    },
  })

  // Convert backend response to frontend format
  const summary: UsageSummary[] = []
  
  // Add totals by resource type
  if (response.totals) {
    Object.entries(response.totals).forEach(([resourceType, count]) => {
      summary.push({
        resourceType,
        count,
        period: response.period || params.period || 'day',
      })
    })
  }
  
  // Add breakdown by resource if available
  if (response.by_resource) {
    Object.entries(response.by_resource).forEach(([resourceType, resourceData]) => {
      const totalCount = Object.values(resourceData).reduce((sum, count) => sum + count, 0)
      if (totalCount > 0) {
        const existing = summary.find(s => s.resourceType === resourceType)
        if (existing) {
          existing.count = totalCount
        } else {
          summary.push({
            resourceType,
            count: totalCount,
            period: response.period || params.period || 'day',
          })
        }
      }
    })
  }

  return {
    summary,
    period: response.period || params.period || 'day',
  }
}

export interface GetUsageDetailsParams {
  tenantId: string
  metricType: string
  fromDate: string
  toDate: string
  resourceId?: string
}

export interface UsageDetail {
  tenantId: string
  resourceType: string
  count: number
  date: string
  metadata?: Record<string, unknown>
}

export interface UsageDetailsResponse {
  items: UsageDetail[]
  total: number
}

export async function getUsageDetails(params: GetUsageDetailsParams): Promise<UsageDetailsResponse> {
  const response = await httpClient.get<{
    tenant_id: string
    metric_type: string
    from_date: string
    to_date: string
    records: Array<{
      metric_type: string
      resource_id?: string
      period_start: string
      period_end: string
      count: number
      bytes_value?: number
    }>
    total_count: number
  }>('/usage/details', {
    params: {
      tenant_id: params.tenantId,
      metric_type: params.metricType,
      from_date: params.fromDate,
      to_date: params.toDate,
      resource_id: params.resourceId,
    },
  })

  return {
    items: (response.records || []).map((item: any) => ({
      tenantId: response.tenant_id || params.tenantId,
      resourceType: item.metric_type || '',
      count: item.count || 0,
      date: item.period_start || item.period_end || '',
      metadata: {
        resource_id: item.resource_id,
        bytes_value: item.bytes_value,
      },
    })),
    total: response.total_count || 0,
  }
}

export interface ExportUsageParams {
  tenantId: string
  period: 'day' | 'week' | 'month'
  format?: 'csv' | 'json'
  fromDate?: string
  toDate?: string
}

export async function exportUsage(params: ExportUsageParams): Promise<Blob> {
  const response = await httpClient.get('/usage/export', {
    params: {
      tenant_id: params.tenantId,
      period: params.period,
      from_date: params.fromDate,
      to_date: params.toDate,
      format: params.format || 'csv',
    },
    responseType: 'blob',
  })
  return response as unknown as Blob
}
