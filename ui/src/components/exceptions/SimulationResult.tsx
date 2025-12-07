import {
  Box,
  Card,
  CardContent,
  Typography,
  Alert,
  Stack,
  Grid,
  Divider,
  Button,
} from '@mui/material'
import CardSkeleton from '../common/CardSkeleton.tsx'
import { SeverityChip, StatusChip } from '../common'
import { useSimulation } from '../../hooks/useSimulation.ts'
import { useExceptionDetail } from '../../hooks/useExceptions.ts'
import { useNavigate } from 'react-router-dom'

/**
 * Props for SimulationResult component
 */
export interface SimulationResultProps {
  /** Original exception identifier */
  exceptionId: string
  /** Simulation identifier */
  simulationId: string
}


/**
 * Compare two values and determine if they're different
 */
function valuesAreDifferent(original: unknown, simulated: unknown): boolean {
  if (original === simulated) {
    return false
  }
  // Handle null/undefined
  if (original == null || simulated == null) {
    return original !== simulated
  }
  // String comparison
  if (typeof original === 'string' && typeof simulated === 'string') {
    return original !== simulated
  }
  // Number comparison
  if (typeof original === 'number' && typeof simulated === 'number') {
    return original !== simulated
  }
  // Array comparison (simple)
  if (Array.isArray(original) && Array.isArray(simulated)) {
    return JSON.stringify(original) !== JSON.stringify(simulated)
  }
  // Object comparison (simple)
  if (typeof original === 'object' && typeof simulated === 'object') {
    return JSON.stringify(original) !== JSON.stringify(simulated)
  }
  return true
}

/**
 * Render a comparison field
 */
interface ComparisonFieldProps {
  label: string
  original: unknown
  simulated: unknown
}

function ComparisonField({ label, original, simulated }: ComparisonFieldProps) {
  const isDifferent = valuesAreDifferent(original, simulated)
  const originalStr = original == null ? '—' : String(original)
  const simulatedStr = simulated == null ? '—' : String(simulated)

  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
        {label}
      </Typography>
      <Grid container spacing={2}>
        <Grid item xs={6}>
          <Typography
            variant="body2"
            sx={{
              fontWeight: isDifferent ? 'bold' : 'normal',
              color: isDifferent ? 'text.primary' : 'text.secondary',
            }}
          >
            {originalStr}
          </Typography>
        </Grid>
        <Grid item xs={6}>
          <Typography
            variant="body2"
            sx={{
              fontWeight: isDifferent ? 'bold' : 'normal',
              color: isDifferent ? 'success.main' : 'text.secondary',
            }}
          >
            {simulatedStr}
          </Typography>
        </Grid>
      </Grid>
    </Box>
  )
}

/**
 * Simulation Result Component
 * 
 * Displays simulation result and comparison with original exception.
 */
export default function SimulationResult({ exceptionId, simulationId }: SimulationResultProps) {
  const navigate = useNavigate()
  const { data: simulationData, isLoading: isLoadingSimulation, isError: isSimulationError, error: simulationError } = useSimulation(simulationId)
  const { data: originalData, isLoading: isLoadingOriginal } = useExceptionDetail(exceptionId)

  // Extract key fields from simulation data
  const simulatedException = simulationData?.simulated_exception as Record<string, unknown> | undefined
  const originalException = originalData?.exception as Record<string, unknown> | undefined
  const comparison = simulationData?.comparison as Record<string, unknown> | undefined

  // Loading state
  if (isLoadingSimulation || isLoadingOriginal) {
    return (
      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Stack spacing={2}>
            <CardSkeleton lines={4} />
            <CardSkeleton lines={4} />
          </Stack>
        </CardContent>
      </Card>
    )
  }

  // Error state
  if (isSimulationError) {
    return (
      <Alert severity="error" sx={{ mt: 3 }}>
        Failed to load simulation result: {simulationError?.message || 'Unknown error'}
      </Alert>
    )
  }

  if (!simulationData) {
    return (
      <Alert severity="info" sx={{ mt: 3 }}>
        Simulation result not found.
      </Alert>
    )
  }

  // Extract comparison fields
  const originalStatus = originalException?.resolutionStatus as string | undefined
  const simulatedStatus = simulatedException?.resolutionStatus as string | undefined
  const originalSeverity = originalException?.severity as string | undefined
  const simulatedSeverity = simulatedException?.severity as string | undefined

  // Handle back to original view
  const handleBackToOriginal = () => {
    navigate(`/exceptions/${exceptionId}`, { replace: true })
  }

  return (
    <Box sx={{ mt: 3 }}>
      {/* Header with back button */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box>
          <Typography variant="h6">Simulation Result</Typography>
          <Typography variant="caption" color="text.secondary">
            Simulation ID: {simulationId}
          </Typography>
        </Box>
        <Button variant="outlined" onClick={handleBackToOriginal}>
          Back to Original View
        </Button>
      </Box>

      {/* Simulation mode notice */}
      <Alert severity="info" sx={{ mb: 3 }}>
        This is a simulation result. No real actions were taken. The simulation was run with the following overrides:
        {simulationData.overrides_applied && Object.keys(simulationData.overrides_applied).length > 0 ? (
          <Box component="ul" sx={{ mt: 1, mb: 0, pl: 3 }}>
            {Object.entries(simulationData.overrides_applied).map(([key, value]) => (
              <li key={key}>
                <Typography variant="body2">
                  <strong>{key}:</strong> {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                </Typography>
              </li>
            ))}
          </Box>
        ) : (
          <Typography variant="body2" sx={{ mt: 1 }}>
            No overrides were applied.
          </Typography>
        )}
      </Alert>

      {/* Comparison Section */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Comparison with Original
          </Typography>
          <Divider sx={{ mb: 2 }} />

          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Original
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Simulated
              </Typography>
            </Grid>
          </Grid>

          {/* Status comparison */}
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              Status
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                {originalStatus ? (
                  <StatusChip status={originalStatus} size="small" />
                ) : (
                  <Typography variant="body2" color="text.secondary">—</Typography>
                )}
              </Grid>
              <Grid item xs={12} sm={6}>
                {simulatedStatus ? (
                  <StatusChip
                    status={simulatedStatus}
                    size="small"
                    sx={{
                      fontWeight: valuesAreDifferent(originalStatus, simulatedStatus) ? 'bold' : 'normal',
                    }}
                  />
                ) : (
                  <Typography variant="body2" color="text.secondary">—</Typography>
                )}
              </Grid>
            </Grid>
          </Box>

          {/* Severity comparison */}
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              Severity
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                {originalSeverity ? (
                  <SeverityChip severity={originalSeverity} size="small" />
                ) : (
                  <Typography variant="body2" color="text.secondary">—</Typography>
                )}
              </Grid>
              <Grid item xs={12} sm={6}>
                {simulatedSeverity ? (
                  <SeverityChip
                    severity={simulatedSeverity}
                    size="small"
                    sx={{
                      fontWeight: valuesAreDifferent(originalSeverity, simulatedSeverity) ? 'bold' : 'normal',
                    }}
                  />
                ) : (
                  <Typography variant="body2" color="text.secondary">—</Typography>
                )}
              </Grid>
            </Grid>
          </Box>

          {/* Additional comparison fields from comparison object */}
          {comparison && Object.keys(comparison).length > 0 && (
            <>
              <Divider sx={{ my: 2 }} />
              <Typography variant="subtitle2" gutterBottom>
                Additional Comparisons
              </Typography>
              {Object.entries(comparison).map(([key, value]) => {
                if (typeof value === 'object' && value !== null && 'original' in value && 'simulated' in value) {
                  const compValue = value as { original: unknown; simulated: unknown }
                  return (
                    <ComparisonField
                      key={key}
                      label={key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                      original={compValue.original}
                      simulated={compValue.simulated}
                    />
                  )
                }
                return null
              })}
            </>
          )}
        </CardContent>
      </Card>

      {/* Simulated Exception Details */}
      {simulatedException && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Simulated Exception Details
            </Typography>
            <Divider sx={{ mb: 2 }} />
            <Stack spacing={1.5}>
              {Object.entries(simulatedException).map(([key, value]) => {
                // Skip fields already shown in comparison
                if (['resolutionStatus', 'severity'].includes(key)) {
                  return null
                }
                return (
                  <Box key={key}>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                      {key.replace(/([A-Z])/g, ' $1').replace(/^./, (str) => str.toUpperCase())}
                    </Typography>
                    <Typography variant="body2">
                      {typeof value === 'object' && value !== null
                        ? JSON.stringify(value, null, 2)
                        : String(value)}
                    </Typography>
                  </Box>
                )
              })}
            </Stack>
          </CardContent>
        </Card>
      )}
    </Box>
  )
}

