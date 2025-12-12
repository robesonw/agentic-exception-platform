import { useState, useMemo } from 'react'
import {
  Box,
  Card,
  CardContent,
  Typography,
  Alert,
  Stack,
  Chip,
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Button,
} from '@mui/material'
import CardSkeleton from '../common/CardSkeleton.tsx'
import { useExceptionEvents } from '../../hooks/useExceptions.ts'
import { useTenant } from '../../hooks/useTenant.tsx'
import { formatDateTime } from '../../utils/dateFormat.ts'
import type { ExceptionEvent } from '../../api/exceptions.ts'

/**
 * Props for ExceptionTimelineTab component
 */
export interface ExceptionTimelineTabProps {
  /** Exception identifier */
  exceptionId: string
}

/**
 * Format event type for display
 */
function formatEventType(eventType: string): string {
  // Convert camelCase to Title Case
  return eventType
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (str) => str.toUpperCase())
    .trim()
}

/**
 * Get event color based on event type
 */
function getEventColor(eventType: string): 'primary' | 'secondary' | 'success' | 'error' | 'info' | 'warning' {
  if (eventType.includes('Created')) return 'info'
  if (eventType.includes('Completed')) return 'success'
  if (eventType.includes('Approved')) return 'success'
  if (eventType.includes('Rejected') || eventType.includes('Failed')) return 'error'
  if (eventType.includes('Escalated')) return 'warning'
  if (eventType.includes('Evaluated') || eventType.includes('Proposed')) return 'primary'
  return 'secondary'
}

/**
 * Get actor type color
 */
function getActorTypeColor(actorType: string): 'default' | 'primary' | 'secondary' | 'success' | 'error' | 'info' | 'warning' {
  switch (actorType.toLowerCase()) {
    case 'agent':
      return 'primary'
    case 'user':
      return 'success'
    case 'system':
      return 'info'
    default:
      return 'default'
  }
}

/**
 * Format payload summary for display
 */
function formatPayloadSummary(payload: Record<string, unknown>): string {
  if (!payload || Object.keys(payload).length === 0) {
    return 'No additional details'
  }
  
  // Try to extract meaningful summary
  const keys = Object.keys(payload)
  if (keys.length === 1) {
    const value = payload[keys[0]]
    if (typeof value === 'string' && value.length < 100) {
      return `${keys[0]}: ${value}`
    }
  }
  
  // Return a generic summary
  return `${keys.length} field${keys.length !== 1 ? 's' : ''}`
}

/**
 * Event timeline card component
 */
interface EventTimelineCardProps {
  event: ExceptionEvent
  isLast: boolean
}

function EventTimelineCard({ event, isLast }: EventTimelineCardProps) {
  return (
    <Box sx={{ position: 'relative', pb: isLast ? 0 : 3 }}>
      {/* Vertical connector line */}
      {!isLast && (
        <Box
          sx={{
            position: 'absolute',
            left: 20,
            top: 48,
            bottom: 0,
            width: 2,
            bgcolor: 'divider',
          }}
        />
      )}

      {/* Event indicator dot */}
      <Box
        sx={{
          position: 'absolute',
          left: 12,
          top: 12,
          width: 16,
          height: 16,
          borderRadius: '50%',
          bgcolor: (theme) => theme.palette[getEventColor(event.eventType)].main,
          border: (theme) => `2px solid ${theme.palette.background.paper}`,
          zIndex: 1,
        }}
      />

      {/* Card content */}
      <Card sx={{ ml: 4, position: 'relative' }}>
        <CardContent>
          <Stack spacing={1.5}>
            {/* Event type and timestamp */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 1 }}>
              <Chip
                label={formatEventType(event.eventType)}
                color={getEventColor(event.eventType)}
                size="small"
              />
              <Typography variant="caption" color="text.secondary">
                {formatDateTime(event.createdAt)}
              </Typography>
            </Box>

            {/* Actor information */}
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                Actor
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                <Chip
                  label={event.actorType.charAt(0).toUpperCase() + event.actorType.slice(1)}
                  color={getActorTypeColor(event.actorType)}
                  size="small"
                  variant="outlined"
                />
                {event.actorId && (
                  <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                    {event.actorId}
                  </Typography>
                )}
              </Box>
            </Box>

            {/* Payload summary */}
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                Details
              </Typography>
              <Typography variant="body2">{formatPayloadSummary(event.payload)}</Typography>
            </Box>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  )
}

/**
 * Exception Timeline Tab Component
 * 
 * P6-27: Updated to use DB-backed event timeline from /exceptions/{id}/events
 * 
 * Displays the event timeline for an exception, showing all events in chronological order
 * with event type, actor information, timestamps, and payload summaries.
 */
export default function ExceptionTimelineTab({ exceptionId }: ExceptionTimelineTabProps) {
  const { tenantId } = useTenant()
  
  // Filter state
  const [eventTypeFilter, setEventTypeFilter] = useState<string>('')
  const [actorTypeFilter, setActorTypeFilter] = useState<string>('')
  const [dateFromFilter, setDateFromFilter] = useState<string>('')
  const [dateToFilter, setDateToFilter] = useState<string>('')

  // Build API params from filters
  const apiParams = useMemo(() => {
    const params: {
      eventType?: string
      actorType?: string
      dateFrom?: string
      dateTo?: string
    } = {}
    
    if (eventTypeFilter) params.eventType = eventTypeFilter
    if (actorTypeFilter) params.actorType = actorTypeFilter
    if (dateFromFilter) {
      const date = new Date(dateFromFilter)
      params.dateFrom = date.toISOString()
    }
    if (dateToFilter) {
      const date = new Date(dateToFilter)
      date.setHours(23, 59, 59, 999)
      params.dateTo = date.toISOString()
    }
    
    return params
  }, [eventTypeFilter, actorTypeFilter, dateFromFilter, dateToFilter])

  // Fetch events
  const { data, isLoading, isError, error } = useExceptionEvents(exceptionId, apiParams)

  // Handle clear filters
  const handleClearFilters = () => {
    setEventTypeFilter('')
    setActorTypeFilter('')
    setDateFromFilter('')
    setDateToFilter('')
  }

  const hasActiveFilters = Boolean(eventTypeFilter || actorTypeFilter || dateFromFilter || dateToFilter)

  // Loading state
  if (isLoading) {
    return (
      <Stack spacing={2}>
        {[1, 2, 3].map((i) => (
          <CardSkeleton key={i} lines={4} showTitle={false} />
        ))}
      </Stack>
    )
  }

  // Error state
  if (isError) {
    // Check for 404 or tenant mismatch
    const isNotFound = error?.message?.includes('404') || error?.message?.includes('not found')
    const isTenantMismatch = error?.message?.includes('tenant') || error?.message?.includes('403')
    
    return (
      <Alert severity="error">
        {isNotFound
          ? 'Exception not found or does not belong to the current tenant.'
          : isTenantMismatch
          ? 'Tenant mismatch. Please ensure you are viewing the correct tenant.'
          : `Failed to load timeline: ${error?.message || 'Unknown error'}`}
      </Alert>
    )
  }

  // Empty state
  if (!data || !data.items || data.items.length === 0) {
    return (
      <Box>
        {hasActiveFilters && (
          <Alert severity="info" sx={{ mb: 2 }}>
            No events found matching the current filters.
            <Button size="small" onClick={handleClearFilters} sx={{ ml: 2 }}>
              Clear filters
            </Button>
          </Alert>
        )}
        {!hasActiveFilters && (
          <Alert severity="info">
            No events available for this exception yet.
          </Alert>
        )}
      </Box>
    )
  }

  // Events are already sorted chronologically by the backend (oldest first)
  const events = data.items

  return (
    <Box>
      {/* Filter controls */}
      <Paper sx={{ p: 2, mb: 3, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ flexWrap: 'wrap' }}>
          {/* Event Type Filter */}
          <FormControl size="small" sx={{ minWidth: { xs: '100%', sm: 180 } }}>
            <InputLabel>Event Type</InputLabel>
            <Select
              value={eventTypeFilter}
              label="Event Type"
              onChange={(e) => setEventTypeFilter(e.target.value)}
            >
              <MenuItem value="">
                <em>All</em>
              </MenuItem>
              <MenuItem value="ExceptionCreated">Exception Created</MenuItem>
              <MenuItem value="ExceptionNormalized">Exception Normalized</MenuItem>
              <MenuItem value="TriageCompleted">Triage Completed</MenuItem>
              <MenuItem value="PolicyEvaluated">Policy Evaluated</MenuItem>
              <MenuItem value="ResolutionSuggested">Resolution Suggested</MenuItem>
              <MenuItem value="ResolutionApproved">Resolution Approved</MenuItem>
              <MenuItem value="FeedbackCaptured">Feedback Captured</MenuItem>
            </Select>
          </FormControl>

          {/* Actor Type Filter */}
          <FormControl size="small" sx={{ minWidth: { xs: '100%', sm: 150 } }}>
            <InputLabel>Actor Type</InputLabel>
            <Select
              value={actorTypeFilter}
              label="Actor Type"
              onChange={(e) => setActorTypeFilter(e.target.value)}
            >
              <MenuItem value="">
                <em>All</em>
              </MenuItem>
              <MenuItem value="agent">Agent</MenuItem>
              <MenuItem value="user">User</MenuItem>
              <MenuItem value="system">System</MenuItem>
            </Select>
          </FormControl>

          {/* Date From Filter */}
          <TextField
            size="small"
            label="From"
            type="date"
            value={dateFromFilter}
            onChange={(e) => setDateFromFilter(e.target.value)}
            InputLabelProps={{ shrink: true }}
            sx={{ minWidth: { xs: '100%', sm: 150 } }}
          />

          {/* Date To Filter */}
          <TextField
            size="small"
            label="To"
            type="date"
            value={dateToFilter}
            onChange={(e) => setDateToFilter(e.target.value)}
            InputLabelProps={{ shrink: true }}
            sx={{ minWidth: { xs: '100%', sm: 150 } }}
          />

          {/* Clear Filters Button */}
          {hasActiveFilters && (
            <Button variant="outlined" size="small" onClick={handleClearFilters} sx={{ alignSelf: 'flex-end' }}>
              Clear
            </Button>
          )}
        </Stack>
      </Paper>

      {/* Event count info */}
      {data.total > 0 && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
          Showing {events.length} of {data.total} event{data.total !== 1 ? 's' : ''}
          {hasActiveFilters && ' (filtered)'}
        </Typography>
      )}

      {/* Timeline */}
      <Stack spacing={0}>
        {events.map((event, index) => (
          <EventTimelineCard
            key={event.eventId || `${event.eventType}-${event.createdAt}-${index}`}
            event={event}
            isLast={index === events.length - 1}
          />
        ))}
      </Stack>
    </Box>
  )
}

