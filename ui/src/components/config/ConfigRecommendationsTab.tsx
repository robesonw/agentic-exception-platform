import {
  Box,
  Card,
  CardContent,
  Typography,
  Alert,
  Stack,
  Chip,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  LinearProgress,
} from '@mui/material'
import { useGuardrailRecommendations } from '../../hooks/useConfig.ts'
import { useTenant } from '../../hooks/useTenant.tsx'
import TableSkeleton from '../common/TableSkeleton.tsx'
import { formatDateTime } from '../../utils/dateFormat.ts'
import type { GuardrailRecommendation } from '../../types'

/**
 * Props for ConfigRecommendationsTab component
 */
export interface ConfigRecommendationsTabProps {
  /** Optional tenant ID filter */
  tenantId?: string
  /** Optional domain filter */
  domain?: string
}

/**
 * Format confidence score as percentage
 */
function formatConfidence(confidence?: number): string {
  if (confidence === undefined || confidence === null) return '—'
  return `${Math.round(confidence * 100)}%`
}

/**
 * Config Recommendations Tab Component
 * 
 * Displays configuration recommendations (guardrail, policy, severity, playbook).
 * Currently supports guardrail recommendations; other types show placeholders.
 */
export default function ConfigRecommendationsTab({
  tenantId: tenantIdProp,
  domain: domainProp,
}: ConfigRecommendationsTabProps) {
  const { tenantId: tenantIdFromContext, domain: domainFromContext } = useTenant()
  
  // Use props if provided, otherwise fall back to context
  const tenantId = tenantIdProp || tenantIdFromContext || ''
  const domain = domainProp || domainFromContext || ''
  
  // Guardrail recommendations require both tenantId and domain
  const canFetchGuardrailRecommendations = !!tenantId && !!domain

  // Fetch guardrail recommendations (only type currently supported)
  // Hook handles enabled logic internally based on tenantId and domain presence
  const guardrailQuery = useGuardrailRecommendations({
    tenantId: canFetchGuardrailRecommendations ? tenantId : '',
    domain: canFetchGuardrailRecommendations ? domain : '',
  })

  const hasGuardrailData = guardrailQuery.data && guardrailQuery.data.recommendations.length > 0
  const isLoading = guardrailQuery.isLoading
  const hasError = guardrailQuery.isError

  return (
    <Box>
      {/* Phase 5 Notice */}
      <Alert severity="info" sx={{ mb: 3 }}>
        Recommendations are read-only in Phase 4. Review and plan changes in Phase 5.
      </Alert>

      {/* Guardrail Recommendations Section */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Guardrail Recommendations
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            Suggestions for tuning guardrails based on policy violations and performance metrics.
          </Typography>

          {isLoading && <TableSkeleton rowCount={5} columnCount={5} />}

          {hasError && (
            <Alert severity="error">
              Failed to load guardrail recommendations: {guardrailQuery.error?.message || 'Unknown error'}
            </Alert>
          )}

          {!canFetchGuardrailRecommendations && (
            <Alert severity="warning">
              Please select a tenant and domain to view guardrail recommendations.
            </Alert>
          )}

          {canFetchGuardrailRecommendations && !isLoading && !hasError && !hasGuardrailData && (
            <Alert severity="info">
              No guardrail recommendations available for the selected tenant and domain.
            </Alert>
          )}

          {!isLoading && !hasError && hasGuardrailData && (
            <TableContainer component={Paper} variant="outlined">
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Guardrail ID</TableCell>
                    <TableCell>Reason</TableCell>
                    <TableCell>Confidence</TableCell>
                    <TableCell>Proposed Change</TableCell>
                    <TableCell>Created</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {guardrailQuery.data!.recommendations.map((rec: GuardrailRecommendation) => (
                    <TableRow key={rec.guardrailId}>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                          {rec.guardrailId}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{rec.reason}</Typography>
                      </TableCell>
                      <TableCell>
                        <Stack direction="row" spacing={1} alignItems="center">
                          <Chip
                            label={formatConfidence(rec.confidence)}
                            size="small"
                            color={rec.confidence >= 0.8 ? 'success' : rec.confidence >= 0.6 ? 'warning' : 'default'}
                          />
                          {rec.confidence !== undefined && (
                            <Box sx={{ width: 60 }}>
                              <LinearProgress
                                variant="determinate"
                                value={rec.confidence * 100}
                                sx={{ height: 6, borderRadius: 3 }}
                              />
                            </Box>
                          )}
                        </Stack>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 300 }}>
                          {rec.proposedChange
                            ? JSON.stringify(rec.proposedChange, null, 2).substring(0, 100) + '...'
                            : '—'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {formatDateTime(rec.createdAt)}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      <Divider sx={{ my: 3 }} />

      {/* Placeholder Sections for Other Recommendation Types */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Policy Recommendations
          </Typography>
          <Alert severity="info">
            Policy recommendations API coming in Phase 5. This view will show policy tuning suggestions when available.
          </Alert>
        </CardContent>
      </Card>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Severity Recommendations
          </Typography>
          <Alert severity="info">
            Severity recommendations API coming in Phase 5. This view will show severity adjustment suggestions when available.
          </Alert>
        </CardContent>
      </Card>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Playbook Recommendations
          </Typography>
          <Alert severity="info">
            Playbook recommendations API coming in Phase 5. This view will show playbook optimization suggestions when available.
          </Alert>
        </CardContent>
      </Card>
    </Box>
  )
}

