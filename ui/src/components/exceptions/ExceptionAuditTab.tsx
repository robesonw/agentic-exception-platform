import { useMemo, useState } from 'react'
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  Paper,
  Typography,
  Alert,
  Chip,
} from '@mui/material'
import TableSkeleton from '../common/TableSkeleton.tsx'
import { useExceptionAudit } from '../../hooks/useExceptions.ts'
import { formatDateTime } from '../../utils/dateFormat.ts'
import type { AuditEvent } from '../../types'

/**
 * Props for ExceptionAuditTab component
 */
export interface ExceptionAuditTabProps {
  /** Exception identifier */
  exceptionId: string
}

/**
 * Format event type for display
 */
function formatEventType(eventType?: string): string {
  if (!eventType) {
    return 'Unknown'
  }
  return eventType.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
}

/**
 * Get event type color
 */
function getEventTypeColor(eventType?: string): 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' {
  if (!eventType) {
    return 'default'
  }
  const lowerType = eventType.toLowerCase()
  if (lowerType.includes('error') || lowerType.includes('fail')) {
    return 'error'
  }
  if (lowerType.includes('success') || lowerType.includes('complete')) {
    return 'success'
  }
  if (lowerType.includes('warning') || lowerType.includes('alert')) {
    return 'warning'
  }
  if (lowerType.includes('tool') || lowerType.includes('action')) {
    return 'primary'
  }
  if (lowerType.includes('decision') || lowerType.includes('agent')) {
    return 'info'
  }
  return 'default'
}

/**
 * Extract actor from event data
 */
function extractActor(event: AuditEvent): string {
  if (event.data) {
    const data = event.data as Record<string, unknown>
    if (data.agent_name) {
      return String(data.agent_name)
    }
    if (data.actor) {
      return String(data.actor)
    }
    if (data.user_id) {
      return String(data.user_id)
    }
  }
  return 'System'
}

/**
 * Extract action from event
 */
function extractAction(event: AuditEvent): string {
  if (event.event_type) {
    return formatEventType(event.event_type)
  }
  if (event.data) {
    const data = event.data as Record<string, unknown>
    if (data.action) {
      return String(data.action)
    }
  }
  return 'Event'
}

/**
 * Extract details from event data
 */
function extractDetails(event: AuditEvent): string {
  if (event.data) {
    const data = event.data as Record<string, unknown>
    // Exclude fields already shown as actor/action
    const excludeFields = ['agent_name', 'actor', 'user_id', 'action', 'event_type']
    const details: string[] = []
    
    Object.entries(data).forEach(([key, value]) => {
      if (!excludeFields.includes(key)) {
        if (typeof value === 'object' && value !== null) {
          details.push(`${key}: ${JSON.stringify(value)}`)
        } else {
          details.push(`${key}: ${String(value)}`)
        }
      }
    })
    
    if (details.length > 0) {
      return details.join('; ')
    }
  }
  return '—'
}

type SortDirection = 'asc' | 'desc'

/**
 * Exception Audit Tab Component
 * 
 * Displays the audit trail for an exception, showing all events
 * (agent events, tool calls, decisions) in chronological order.
 */
export default function ExceptionAuditTab({ exceptionId }: ExceptionAuditTabProps) {
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc') // Newest first by default

  const { data, isLoading, isError, error } = useExceptionAudit(exceptionId)

  // Sort events by timestamp
  const sortedEvents = useMemo(() => {
    if (!data?.events) {
      return []
    }
    const events = [...data.events]
    events.sort((a, b) => {
      const dateA = new Date(a.timestamp).getTime()
      const dateB = new Date(b.timestamp).getTime()
      return sortDirection === 'desc' ? dateB - dateA : dateA - dateB
    })
    return events
  }, [data?.events, sortDirection])

  // Handle sort change
  const handleSortChange = () => {
    setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))
  }

  // Loading state
  if (isLoading) {
    return <TableSkeleton rowCount={5} columnCount={4} />
  }

  // Error state
  if (isError) {
    return (
      <Alert severity="error">
        Failed to load audit trail: {error?.message || 'Unknown error'}
        <br />
        <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>
          If this exception was just created, audit events may not be available yet. Try refreshing the page.
        </Typography>
      </Alert>
    )
  }

  // Empty state
  if (!data || !data.events || data.events.length === 0) {
    return (
      <Alert severity="info">
        No audit entries recorded for this exception.
      </Alert>
    )
  }

  return (
    <Box>
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>
                <TableSortLabel
                  active={true}
                  direction={sortDirection}
                  onClick={handleSortChange}
                >
                  Timestamp
                </TableSortLabel>
              </TableCell>
              <TableCell>Actor</TableCell>
              <TableCell>Action</TableCell>
              <TableCell>Details</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sortedEvents.map((event, index) => {
              const actor = extractActor(event)
              const action = extractAction(event)
              const details = extractDetails(event)

              return (
                <TableRow key={`${event.timestamp}-${index}`} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                      {formatDateTime(event.timestamp)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{actor}</Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={action}
                      size="small"
                      color={getEventTypeColor(event.event_type)}
                    />
                  </TableCell>
                  <TableCell>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{
                        maxWidth: 400,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                      title={details}
                    >
                      {details}
                    </Typography>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  )
}

