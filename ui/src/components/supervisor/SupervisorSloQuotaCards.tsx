import {
  Box,
  Card,
  CardContent,
  Typography,
  Alert,
  Stack,
  Chip,
  Grid,
} from '@mui/material'

/**
 * Props for SupervisorSloQuotaCards component
 */
export interface SupervisorSloQuotaCardsProps {
  /** Filter parameters */
  filters: {
    tenantId?: string
    domain?: string
    from_ts?: string
    to_ts?: string
  }
}

/**
 * Supervisor SLO/Quota Cards Component
 * 
 * Displays SLO metrics and quota usage cards.
 * Currently shows placeholders as endpoints are not yet available in Phase 4.
 * Will be wired to real endpoints when available in Phase 5.
 */
export default function SupervisorSloQuotaCards({ filters: _filters }: SupervisorSloQuotaCardsProps) {
  // Note: Backend endpoints /ui/supervisor/slo-summary and /ui/supervisor/quota-summary
  // are not yet available in Phase 4. This component shows placeholders.
  // When endpoints are added, uncomment the hooks below and implement the real data display.

  // TODO: When endpoints are available, uncomment these:
  // const { data: sloData, isLoading: isLoadingSlo, isError: isSloError } = useSupervisorSloSummary(_filters)
  // const { data: quotaData, isLoading: isLoadingQuota, isError: isQuotaError } = useSupervisorQuotaSummary(_filters)

  const endpointsAvailable = false // Set to true when backend endpoints are implemented

  // Placeholder: Show "Coming in Phase 5" messages
  if (!endpointsAvailable) {
    return (
      <Box>
        <Typography variant="h6" gutterBottom sx={{ mt: 3, mb: 2 }}>
          SLO & Quota Metrics
        </Typography>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Stack spacing={2}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="h6">SLO Metrics</Typography>
                    <Chip label="Coming Soon" size="small" color="info" />
                  </Box>
                  <Alert severity="info">
                    SLO metrics (latency, throughput, error rates, MTTR, auto-resolution rate) will be available in Phase 5.
                  </Alert>
                </Stack>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Stack spacing={2}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="h6">Quota Usage</Typography>
                    <Chip label="Coming Soon" size="small" color="info" />
                  </Box>
                  <Alert severity="info">
                    Quota metrics (LLM tokens, vector DB queries, tool calls) will be available in Phase 5.
                  </Alert>
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Box>
    )
  }

  // Future implementation when endpoints are available:
  // When backend endpoints /ui/supervisor/slo-summary and /ui/supervisor/quota-summary are added:
  // 1. Add API functions to ui/src/api/supervisor.ts
  // 2. Add hooks to ui/src/hooks/useSupervisor.ts
  // 3. Add types to ui/src/types/supervisor.ts
  // 4. Uncomment hooks above and implement data display similar to the structure shown in comments below
  // 5. Set endpointsAvailable = true
}

