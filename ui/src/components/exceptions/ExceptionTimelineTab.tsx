import { Box, Card, CardContent, Typography, Alert, Stack, Chip, LinearProgress } from '@mui/material'
import CardSkeleton from '../common/CardSkeleton.tsx'
import { useTimeline } from '../../hooks/useExplanations.ts'
import { formatDateTime } from '../../utils/dateFormat.ts'
import type { TimelineEntry, TimelineStage } from '../../types'

/**
 * Props for ExceptionTimelineTab component
 */
export interface ExceptionTimelineTabProps {
  /** Exception identifier */
  exceptionId: string
}

/**
 * Format stage name for display (capitalize first letter)
 */
function formatStageName(stage: TimelineStage): string {
  return stage.charAt(0).toUpperCase() + stage.slice(1)
}

/**
 * Get stage color for visual distinction
 */
function getStageColor(stage: TimelineStage): 'primary' | 'secondary' | 'success' | 'error' | 'info' | 'warning' {
  switch (stage) {
    case 'intake':
      return 'info'
    case 'triage':
      return 'primary'
    case 'policy':
      return 'warning'
    case 'resolution':
      return 'success'
    case 'feedback':
      return 'secondary'
    default:
      return 'info'
  }
}

/**
 * Format confidence score as percentage
 */
function formatConfidence(confidence?: number | null): string {
  if (confidence === null || confidence === undefined) {
    return 'N/A'
  }
  return `${Math.round(confidence * 100)}%`
}

/**
 * Timeline entry card component
 */
interface TimelineEntryCardProps {
  entry: TimelineEntry
  isLast: boolean
}

function TimelineEntryCard({ entry, isLast }: TimelineEntryCardProps) {
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

      {/* Stage indicator dot */}
      <Box
        sx={{
          position: 'absolute',
          left: 12,
          top: 12,
          width: 16,
          height: 16,
          borderRadius: '50%',
          bgcolor: (theme) => theme.palette[getStageColor(entry.stage)].main,
          border: (theme) => `2px solid ${theme.palette.background.paper}`,
          zIndex: 1,
        }}
      />

      {/* Card content */}
      <Card sx={{ ml: 4, position: 'relative' }}>
        <CardContent>
          <Stack spacing={1.5}>
            {/* Stage name and timestamp */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 1 }}>
              <Chip
                label={formatStageName(entry.stage)}
                color={getStageColor(entry.stage)}
                size="small"
              />
              <Typography variant="caption" color="text.secondary">
                {formatDateTime(entry.timestamp)}
              </Typography>
            </Box>

            {/* Decision */}
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                Decision
              </Typography>
              <Typography variant="body2">{entry.decision}</Typography>
            </Box>

            {/* Confidence score */}
            {entry.confidence !== null && entry.confidence !== undefined && (
              <Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                  <Typography variant="caption" color="text.secondary">
                    Confidence
                  </Typography>
                  <Typography variant="caption" fontWeight="medium">
                    {formatConfidence(entry.confidence)}
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={(entry.confidence || 0) * 100}
                  sx={{ height: 6, borderRadius: 1 }}
                />
              </Box>
            )}

            {/* Evidence IDs (if available) */}
            {entry.evidenceIds && entry.evidenceIds.length > 0 && (
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                  Evidence IDs
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {entry.evidenceIds.map((evidenceId) => (
                    <Chip
                      key={evidenceId}
                      label={evidenceId}
                      size="small"
                      variant="outlined"
                      sx={{ fontFamily: 'monospace', fontSize: '0.7rem' }}
                    />
                  ))}
                </Box>
              </Box>
            )}
          </Stack>
        </CardContent>
      </Card>
    </Box>
  )
}

/**
 * Exception Timeline Tab Component
 * 
 * Displays the decision timeline for an exception, showing all agent stages
 * (Intake → Triage → Policy → Resolution → Feedback) with their decisions,
 * confidence scores, and timestamps.
 */
export default function ExceptionTimelineTab({ exceptionId }: ExceptionTimelineTabProps) {
  const { data, isLoading, isError, error } = useTimeline(exceptionId)

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
    return (
      <Alert severity="error">
        Failed to load timeline: {error?.message || 'Unknown error'}
      </Alert>
    )
  }

  // Empty state
  if (!data || !data.entries || data.entries.length === 0) {
    return (
      <Alert severity="info">
        No timeline data available for this exception.
      </Alert>
    )
  }

  const entries = data.entries

  return (
    <Box>
      <Stack spacing={0}>
        {entries.map((entry, index) => (
          <TimelineEntryCard
            key={`${entry.stage}-${entry.timestamp}-${index}`}
            entry={entry}
            isLast={index === entries.length - 1}
          />
        ))}
      </Stack>
    </Box>
  )
}

