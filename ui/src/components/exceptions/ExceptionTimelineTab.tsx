import React, { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
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
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import PlaylistPlayIcon from '@mui/icons-material/PlaylistPlay'
import BuildIcon from '@mui/icons-material/Build'
import CardSkeleton from '../common/CardSkeleton.tsx'
import { useExceptionEvents } from '../../hooks/useExceptions.ts'
import { useTenant } from '../../hooks/useTenant.tsx'
import { formatDateTime } from '../../utils/dateFormat.ts'
import { useToolExecutions, useToolsList } from '../../hooks/useTools.ts'
import type { ExceptionEvent } from '../../api/exceptions.ts'
import type { ToolExecution } from '../../api/tools.ts'

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
  // Phase 7 P7-18: Playbook events
  if (eventType === 'PlaybookStarted') return 'info'
  if (eventType === 'PlaybookStepCompleted') return 'success'
  if (eventType === 'PlaybookCompleted') return 'success'
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
 * Truncate output summary for display
 */
function truncateOutputSummary(outputPayload: Record<string, any> | null, maxLength: number = 100): string {
  if (!outputPayload || Object.keys(outputPayload).length === 0) {
    return 'No output'
  }
  
  const jsonString = JSON.stringify(outputPayload, null, 2)
  if (jsonString.length <= maxLength) {
    return jsonString
  }
  
  return jsonString.substring(0, maxLength) + '...'
}

/**
 * Get execution status color
 */
function getExecutionStatusColor(status: string): 'success' | 'error' | 'warning' | 'info' | 'default' {
  switch (status) {
    case 'succeeded':
      return 'success'
    case 'failed':
      return 'error'
    case 'running':
      return 'warning'
    case 'requested':
      return 'info'
    default:
      return 'default'
  }
}

/**
 * Format playbook event details for display
 * Phase 7 P7-18: Extracts playbook-specific details from event payload
 */
function formatPlaybookEventDetails(eventType: string, payload: Record<string, unknown>): React.ReactNode {
  if (!payload) return null

  const details: React.ReactNode[] = []

  if (eventType === 'PlaybookStarted') {
    if (payload.playbook_id != null) {
      details.push(
        <Typography key="playbook_id" variant="body2" component="span">
          <strong>Playbook ID:</strong> {String(payload.playbook_id)}
        </Typography>
      )
    }
    if (payload.playbook_name) {
      details.push(
        <Typography key="playbook_name" variant="body2" component="span">
          <strong>Name:</strong> {String(payload.playbook_name)}
        </Typography>
      )
    }
    if (payload.playbook_version != null) {
      details.push(
        <Typography key="playbook_version" variant="body2" component="span">
          <strong>Version:</strong> {String(payload.playbook_version)}
        </Typography>
      )
    }
    if (payload.total_steps != null) {
      details.push(
        <Typography key="total_steps" variant="body2" component="span">
          <strong>Total Steps:</strong> {String(payload.total_steps)}
        </Typography>
      )
    }
  } else if (eventType === 'PlaybookStepCompleted') {
    if (payload.playbook_id != null) {
      details.push(
        <Typography key="playbook_id" variant="body2" component="span">
          <strong>Playbook ID:</strong> {String(payload.playbook_id)}
        </Typography>
      )
    }
    if (payload.step_order != null) {
      details.push(
        <Typography key="step_order" variant="body2" component="span">
          <strong>Step Order:</strong> {String(payload.step_order)}
        </Typography>
      )
    }
    if (payload.step_name) {
      details.push(
        <Typography key="step_name" variant="body2" component="span">
          <strong>Step Name:</strong> {String(payload.step_name)}
        </Typography>
      )
    }
    if (payload.action_type) {
      details.push(
        <Typography key="action_type" variant="body2" component="span">
          <strong>Action Type:</strong> {String(payload.action_type)}
        </Typography>
      )
    }
    if (payload.notes) {
      details.push(
        <Typography key="notes" variant="body2" component="span" sx={{ fontStyle: 'italic' }}>
          <strong>Notes:</strong> {String(payload.notes)}
        </Typography>
      )
    }
  } else if (eventType === 'PlaybookCompleted') {
    if (payload.playbook_id != null) {
      details.push(
        <Typography key="playbook_id" variant="body2" component="span">
          <strong>Playbook ID:</strong> {String(payload.playbook_id)}
        </Typography>
      )
    }
    if (payload.total_steps != null) {
      details.push(
        <Typography key="total_steps" variant="body2" component="span">
          <strong>Total Steps:</strong> {String(payload.total_steps)}
        </Typography>
      )
    }
    if (payload.notes) {
      details.push(
        <Typography key="notes" variant="body2" component="span" sx={{ fontStyle: 'italic' }}>
          <strong>Notes:</strong> {String(payload.notes)}
        </Typography>
      )
    }
  }

  if (details.length === 0) {
    return formatPayloadSummary(payload)
  }

  return (
    <Stack spacing={0.5}>
      {details}
    </Stack>
  )
}

/**
 * Tool execution timeline card component
 */
interface ToolExecutionTimelineCardProps {
  execution: ToolExecution
  toolName?: string
  isLast: boolean
}

function ToolExecutionTimelineCard({ execution, toolName, isLast }: ToolExecutionTimelineCardProps) {
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
          bgcolor: (theme) => theme.palette[getExecutionStatusColor(execution.status)].main,
          border: (theme) => `2px solid ${theme.palette.background.paper}`,
          zIndex: 1,
        }}
      />

      {/* Card content */}
      <Card sx={{ ml: 4, position: 'relative' }}>
        <CardContent>
          <Stack spacing={1.5}>
            {/* Tool name, status, and timestamp */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <BuildIcon sx={{ fontSize: 16, color: 'primary.main' }} />
                <Chip
                  label="Tool Execution"
                  color="primary"
                  size="small"
                />
                {toolName && (
                  <Typography variant="body2" sx={{ fontWeight: 500, ml: 0.5 }}>
                    {toolName}
                  </Typography>
                )}
                <Chip
                  label={execution.status.charAt(0).toUpperCase() + execution.status.slice(1)}
                  color={getExecutionStatusColor(execution.status)}
                  size="small"
                  variant="outlined"
                />
              </Box>
              <Typography variant="caption" color="text.secondary">
                {formatDateTime(execution.createdAt)}
              </Typography>
            </Box>

            {/* Actor information */}
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                Actor
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                <Chip
                  label={execution.requestedByActorType.charAt(0).toUpperCase() + execution.requestedByActorType.slice(1)}
                  color={getActorTypeColor(execution.requestedByActorType)}
                  size="small"
                  variant="outlined"
                />
                <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                  {execution.requestedByActorId}
                </Typography>
              </Box>
            </Box>

            {/* Output summary */}
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                Output Summary
              </Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem', wordBreak: 'break-word' }}>
                {truncateOutputSummary(execution.outputPayload)}
              </Typography>
              {execution.errorMessage && (
                <Alert severity="error" sx={{ mt: 1 }}>
                  <Typography variant="body2">{execution.errorMessage}</Typography>
                </Alert>
              )}
            </Box>

            {/* Link to execution detail */}
            <Box>
              <Button
                component={Link}
                to={`/tools/${execution.toolId}`}
                size="small"
                variant="outlined"
                startIcon={<BuildIcon />}
              >
                View Tool Details
              </Button>
            </Box>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  )
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
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                {/* Phase 7 P7-18: Playbook event icon/badge */}
                {event.eventType === 'PlaybookStarted' && (
                  <PlayArrowIcon sx={{ fontSize: 16, color: 'info.main' }} />
                )}
                {event.eventType === 'PlaybookStepCompleted' && (
                  <CheckCircleIcon sx={{ fontSize: 16, color: 'success.main' }} />
                )}
                {event.eventType === 'PlaybookCompleted' && (
                  <PlaylistPlayIcon sx={{ fontSize: 16, color: 'success.main' }} />
                )}
                <Chip
                  label={formatEventType(event.eventType)}
                  color={getEventColor(event.eventType)}
                  size="small"
                />
              </Box>
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

            {/* Payload summary or playbook event details */}
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                Details
              </Typography>
              {/* Phase 7 P7-18: Special rendering for playbook events */}
              {['PlaybookStarted', 'PlaybookStepCompleted', 'PlaybookCompleted'].includes(event.eventType) ? (
                formatPlaybookEventDetails(event.eventType, event.payload)
              ) : (
                <Typography variant="body2">{formatPayloadSummary(event.payload)}</Typography>
              )}
            </Box>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  )
}

/**
 * Unified timeline item type
 */
type TimelineItem = 
  | { type: 'event'; data: ExceptionEvent }
  | { type: 'toolExecution'; data: ToolExecution; toolName?: string }

/**
 * Exception Timeline Tab Component
 * 
 * P6-27: Updated to use DB-backed event timeline from /exceptions/{id}/events
 * P8-13: Added tool execution events to timeline
 * 
 * Displays the event timeline for an exception, showing all events in chronological order
 * with event type, actor information, timestamps, and payload summaries.
 * Also displays tool execution events with tool name, status, timestamp, and output summary.
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

  // Fetch exception events
  const { data: eventsData, isLoading: isLoadingEvents, isError: isErrorEvents, error: eventsError } = useExceptionEvents(exceptionId, apiParams)
  
  // Fetch tool executions for this exception
  const { data: executionsData, isLoading: isLoadingExecutions } = useToolExecutions({
    exception_id: exceptionId,
  })

  // Get unique tool IDs from executions
  const toolIds = useMemo(() => {
    if (!executionsData?.items) return []
    return Array.from(new Set(executionsData.items.map(e => e.toolId)))
  }, [executionsData])

  // Fetch all tools to get names (we'll fetch all tools and filter by IDs)
  // For MVP, we'll fetch tools individually but in a way that doesn't violate hooks rules
  // We'll use a single query to get all tools and filter client-side
  const { data: allToolsData } = useToolsList({ scope: 'all' })

  // Create tool name map
  const toolNameMap = useMemo(() => {
    const map = new Map<number, string>()
    if (allToolsData?.items) {
      allToolsData.items.forEach(tool => {
        if (toolIds.includes(tool.toolId)) {
          map.set(tool.toolId, tool.name)
        }
      })
    }
    return map
  }, [allToolsData, toolIds])

  // Merge events and tool executions into unified timeline
  const timelineItems = useMemo((): TimelineItem[] => {
    const items: TimelineItem[] = []
    
    // Add exception events
    if (eventsData?.items) {
      eventsData.items.forEach(event => {
        items.push({ type: 'event', data: event })
      })
    }
    
    // Add tool executions
    if (executionsData?.items) {
      executionsData.items.forEach(execution => {
        items.push({
          type: 'toolExecution',
          data: execution,
          toolName: toolNameMap.get(execution.toolId),
        })
      })
    }
    
    // Sort by timestamp (oldest first)
    items.sort((a, b) => {
      const timeA = a.type === 'event' ? a.data.createdAt : a.data.createdAt
      const timeB = b.type === 'event' ? b.data.createdAt : b.data.createdAt
      return new Date(timeA).getTime() - new Date(timeB).getTime()
    })
    
    return items
  }, [eventsData, executionsData, toolNameMap])

  const isLoading = isLoadingEvents || isLoadingExecutions
  const isError = isErrorEvents
  const error = eventsError

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
        <br />
        <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>
          If this exception was just created, events may not be available yet. Try refreshing the page.
        </Typography>
      </Alert>
    )
  }

  // Empty state
  if (!isLoading && timelineItems.length === 0) {
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
            No events or tool executions available for this exception yet.
            <br />
            <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>
              Events will appear here as the exception is processed through the pipeline stages.
            </Typography>
          </Alert>
        )}
      </Box>
    )
  }

  const totalEvents = (eventsData?.total || 0) + (executionsData?.total || 0)

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
              {/* Phase 7 P7-18: Playbook event types */}
              <MenuItem value="PlaybookStarted">Playbook Started</MenuItem>
              <MenuItem value="PlaybookStepCompleted">Playbook Step Completed</MenuItem>
              <MenuItem value="PlaybookCompleted">Playbook Completed</MenuItem>
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
      {totalEvents > 0 && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
          Showing {timelineItems.length} of {totalEvents} item{totalEvents !== 1 ? 's' : ''}
          {hasActiveFilters && ' (filtered)'}
        </Typography>
      )}

      {/* Timeline */}
      <Stack spacing={0}>
        {timelineItems.map((item, index) => {
          if (item.type === 'toolExecution') {
            return (
              <ToolExecutionTimelineCard
                key={`tool-execution-${item.data.executionId}`}
                execution={item.data}
                toolName={item.toolName}
                isLast={index === timelineItems.length - 1}
              />
            )
          } else {
            return (
              <EventTimelineCard
                key={item.data.eventId || `event-${item.data.eventType}-${item.data.createdAt}-${index}`}
                event={item.data}
                isLast={index === timelineItems.length - 1}
              />
            )
          }
        })}
      </Stack>
    </Box>
  )
}

