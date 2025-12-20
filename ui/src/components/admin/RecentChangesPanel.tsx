/**
 * Recent Changes Panel Component - Phase 12+ Governance & Audit Polish
 *
 * Displays recent governance audit events for an entity or tenant.
 * Can be embedded in detail dialogs or entity pages.
 */

import { useQuery } from '@tanstack/react-query'
import {
  Box,
  Typography,
  Paper,
  Skeleton,
  Chip,
  Tooltip,
  Button,
  Alert,
  Divider,
} from '@mui/material'
import HistoryIcon from '@mui/icons-material/History'
import { Link as RouterLink } from 'react-router-dom'
import {
  getRecentChangesForEntity,
  getRecentChangesByTenant,
  type GovernanceAuditEvent,
  getEntityTypeLabel,
  getActionLabel,
  getActionColor,
} from '../../api/governanceAudit'
import { formatRelativeTime } from '../../utils/dateFormat'

interface RecentChangesPanelProps {
  /**
   * Entity type for entity-specific changes
   */
  entityType?: string
  /**
   * Entity ID for entity-specific changes
   */
  entityId?: string
  /**
   * Tenant ID for tenant-scoped changes or tenant-level changes
   */
  tenantId?: string
  /**
   * Entity types to filter when showing tenant-level changes
   */
  entityTypes?: string[]
  /**
   * Maximum number of events to show
   */
  limit?: number
  /**
   * Title for the panel
   */
  title?: string
  /**
   * Whether to show the "View All" link
   */
  showViewAll?: boolean
}

export default function RecentChangesPanel({
  entityType,
  entityId,
  tenantId,
  entityTypes,
  limit = 5,
  title = 'Recent Changes',
  showViewAll = true,
}: RecentChangesPanelProps) {
  // Determine whether to fetch entity-specific or tenant-level changes
  const isEntitySpecific = Boolean(entityType && entityId)
  const isTenantLevel = !isEntitySpecific && Boolean(tenantId)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: isEntitySpecific
      ? ['recent-changes-entity', entityType, entityId, tenantId, limit]
      : ['recent-changes-tenant', tenantId, entityTypes, limit],
    queryFn: () => {
      if (isEntitySpecific) {
        return getRecentChangesForEntity(entityType!, entityId!, tenantId, limit)
      } else if (isTenantLevel) {
        return getRecentChangesByTenant(tenantId!, entityTypes, limit)
      }
      return Promise.resolve({ items: [], total: 0 })
    },
    enabled: isEntitySpecific || isTenantLevel,
    staleTime: 30000, // Cache for 30 seconds
  })

  const events = data?.items || []

  // Build the "View All" URL
  const viewAllUrl = isEntitySpecific
    ? `/admin/audit?entity_type=${entityType}&entity_id=${entityId}${tenantId ? `&tenant_id=${tenantId}` : ''}`
    : tenantId
      ? `/admin/audit?tenant_id=${tenantId}`
      : '/admin/audit'

  if (isError) {
    return (
      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          <HistoryIcon sx={{ mr: 0.5, verticalAlign: 'middle', fontSize: 16 }} />
          {title}
        </Typography>
        <Alert severity="error" sx={{ mt: 1 }}>
          Failed to load recent changes
        </Alert>
      </Paper>
    )
  }

  return (
    <Paper sx={{ p: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle2" color="text.secondary">
          <HistoryIcon sx={{ mr: 0.5, verticalAlign: 'middle', fontSize: 16 }} />
          {title}
        </Typography>
        {showViewAll && events.length > 0 && (
          <Button
            component={RouterLink}
            to={viewAllUrl}
            size="small"
            sx={{ textTransform: 'none' }}
          >
            View All
          </Button>
        )}
      </Box>

      {isLoading ? (
        <Box>
          {[1, 2, 3].map((i) => (
            <Box key={i} sx={{ py: 1 }}>
              <Skeleton variant="text" width="60%" />
              <Skeleton variant="text" width="40%" />
            </Box>
          ))}
        </Box>
      ) : events.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
          No recent changes
        </Typography>
      ) : (
        <Box>
          {events.map((event, idx) => (
            <Box key={event.id}>
              <Box
                sx={{
                  py: 1,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                }}
              >
                <Box sx={{ flex: 1, mr: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
                    <Chip
                      label={getActionLabel(event.action)}
                      size="small"
                      color={getActionColor(event.action)}
                      sx={{ height: 20, fontSize: '0.7rem' }}
                    />
                    {!isEntitySpecific && (
                      <Chip
                        label={getEntityTypeLabel(event.entity_type)}
                        size="small"
                        variant="outlined"
                        sx={{ height: 20, fontSize: '0.7rem' }}
                      />
                    )}
                  </Box>
                  <Typography variant="body2" sx={{ mt: 0.5 }}>
                    {event.diff_summary || event.event_type}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    by {event.actor_id} • {formatRelativeTime(event.created_at)}
                  </Typography>
                </Box>
              </Box>
              {idx < events.length - 1 && <Divider />}
            </Box>
          ))}
        </Box>
      )}
    </Paper>
  )
}

/**
 * Compact version for embedding in small spaces
 */
export function RecentChangesCompact({
  entityType,
  entityId,
  tenantId,
  limit = 3,
}: Omit<RecentChangesPanelProps, 'title' | 'showViewAll'>) {
  const { data, isLoading } = useQuery({
    queryKey: ['recent-changes-compact', entityType, entityId, tenantId, limit],
    queryFn: () => getRecentChangesForEntity(entityType!, entityId!, tenantId, limit),
    enabled: !!entityType && !!entityId,
    staleTime: 30000,
  })

  const events = data?.items || []

  if (isLoading) {
    return <Skeleton variant="text" width={150} />
  }

  if (events.length === 0) {
    return (
      <Typography variant="caption" color="text.secondary">
        No changes recorded
      </Typography>
    )
  }

  const lastEvent = events[0]
  return (
    <Tooltip
      title={
        <Box>
          <Typography variant="body2" sx={{ fontWeight: 500 }}>
            Last {events.length} changes:
          </Typography>
          {events.map((e) => (
            <Typography key={e.id} variant="caption" component="div">
              • {getActionLabel(e.action)} by {e.actor_id} ({formatRelativeTime(e.created_at)})
            </Typography>
          ))}
        </Box>
      }
    >
      <Typography variant="caption" color="text.secondary" sx={{ cursor: 'help' }}>
        Last changed by {lastEvent.actor_id} ({formatRelativeTime(lastEvent.created_at)})
      </Typography>
    </Tooltip>
  )
}
