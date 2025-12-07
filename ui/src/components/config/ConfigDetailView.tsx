import { useState } from 'react'
import { Box, Card, CardContent, Typography, Alert, Stack, Chip, Divider, Paper, Grid, Button } from '@mui/material'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import CardSkeleton from '../common/CardSkeleton.tsx'
import {
  useDomainPackDetail,
  useTenantPolicyDetail,
  usePlaybookDetail,
  useConfigHistory,
} from '../../hooks/useConfig.ts'
import { formatDateTime } from '../../utils/dateFormat.ts'
import type { ConfigDetailResponse } from '../../types'
import ConfigDiffDialog from './ConfigDiffDialog.tsx'
import type { UIConfigType } from './ConfigDiffDialog.tsx'

/**
 * Config type for detail view
 */
export type ConfigType = 'domain-packs' | 'tenant-policies' | 'playbooks'

/**
 * Props for ConfigDetailView component
 */
export interface ConfigDetailViewProps {
  /** Configuration type */
  type: ConfigType
  /** Configuration identifier */
  id: string
}

/**
 * Get display name for config type
 */
function getConfigTypeDisplayName(type: ConfigType): string {
  switch (type) {
    case 'domain-packs':
      return 'Domain Pack'
    case 'tenant-policies':
      return 'Tenant Policy Pack'
    case 'playbooks':
      return 'Playbook'
    default:
      return 'Configuration'
  }
}

/**
 * Map UI config type to backend config type for history API
 */
function mapUITypeToBackendType(uiType: ConfigType): 'domain_pack' | 'tenant_policy' | 'playbook' {
  switch (uiType) {
    case 'domain-packs':
      return 'domain_pack'
    case 'tenant-policies':
      return 'tenant_policy'
    case 'playbooks':
      return 'playbook'
    default:
      throw new Error(`Unknown config type: ${uiType}`)
  }
}

/**
 * Config Detail View Component
 * 
 * Displays configuration detail with formatted JSON and metadata.
 * Uses the appropriate hook based on configuration type.
 */
export default function ConfigDetailView({ type, id }: ConfigDetailViewProps) {
  const [diffDialogOpen, setDiffDialogOpen] = useState(false)

  // Select the appropriate hook based on type
  const domainPackQuery = useDomainPackDetail(type === 'domain-packs' ? id : '')
  const tenantPolicyQuery = useTenantPolicyDetail(type === 'tenant-policies' ? id : '')
  const playbookQuery = usePlaybookDetail(type === 'playbooks' ? id : '')

  // Fetch version history for diff comparison
  const historyQuery = useConfigHistory(mapUITypeToBackendType(type), id)

  // Get the active query result
  let query = domainPackQuery
  if (type === 'tenant-policies') {
    query = tenantPolicyQuery
  } else if (type === 'playbooks') {
    query = playbookQuery
  }

  const { data, isLoading, isError, error } = query

  // Loading state
  if (isLoading) {
    return (
      <Box>
        <CardSkeleton lines={8} />
        <Card sx={{ mt: 3 }}>
          <CardContent>
            <Typography variant="body2" color="text.secondary">
              Loading configuration data...
            </Typography>
          </CardContent>
        </Card>
      </Box>
    )
  }

  // Error state
  if (isError) {
    return (
      <Alert severity="error">
        Failed to load configuration: {error?.message || 'Unknown error'}
      </Alert>
    )
  }

  // No data state
  if (!data) {
    return (
      <Alert severity="warning">
        Configuration not found or no data available.
      </Alert>
    )
  }

  const configData: ConfigDetailResponse = data

  // Extract metadata from config data
  const metadata = configData.data as Record<string, unknown>
  const name = metadata.name || metadata.domainName || configData.id
  const version = metadata.version || '—'
  const tenantId = metadata.tenant_id || metadata.tenantId || '—'
  const domain = metadata.domain || metadata.domainName || '—'
  const updatedAt = metadata.timestamp || metadata.updatedAt || metadata.createdAt || null

  // Format JSON string
  const jsonString = JSON.stringify(configData.data, null, 2)

  // Get available versions for diff
  const availableVersions = historyQuery.data?.items || []
  const hasMultipleVersions = availableVersions.length > 1

  return (
    <Box>
      {/* Metadata Summary */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Stack spacing={2}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <Typography variant="h6">{getConfigTypeDisplayName(type)}</Typography>
              <Stack direction="row" spacing={1} alignItems="center">
                {hasMultipleVersions && (
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={() => setDiffDialogOpen(true)}
                  >
                    Compare Versions
                  </Button>
                )}
                <Chip label={configData.type} size="small" color="primary" />
              </Stack>
            </Box>

            <Divider />

            <Grid container spacing={2}>
              <Grid item xs={12} sm={6} md={3}>
                <Typography variant="caption" color="text.secondary">
                  Configuration ID
                </Typography>
                <Typography variant="body1" sx={{ fontFamily: 'monospace', fontSize: '0.875rem', wordBreak: 'break-all' }}>
                  {configData.id}
                </Typography>
              </Grid>

              <Grid item xs={12} sm={6} md={3}>
                <Typography variant="caption" color="text.secondary">
                  Name
                </Typography>
                <Typography variant="body1">
                  {String(name)}
                </Typography>
              </Grid>

              {version !== '—' && (
                <Grid item xs={12} sm={6} md={3}>
                  <Typography variant="caption" color="text.secondary">
                    Version
                  </Typography>
                  <Typography variant="body1">
                    {String(version)}
                  </Typography>
                </Grid>
              )}

              <Grid item xs={12} sm={6} md={3}>
                <Typography variant="caption" color="text.secondary">
                  Tenant ID
                </Typography>
                <Typography variant="body1" sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                  {String(tenantId)}
                </Typography>
              </Grid>

              {domain !== '—' && (
                <Grid item xs={12} sm={6} md={3}>
                  <Typography variant="caption" color="text.secondary">
                    Domain
                  </Typography>
                  <Typography variant="body1">
                    {String(domain)}
                  </Typography>
                </Grid>
              )}

              {updatedAt && (typeof updatedAt === 'string' || updatedAt instanceof Date) && (
                <Grid item xs={12} sm={6} md={3}>
                  <Typography variant="caption" color="text.secondary">
                    Updated
                  </Typography>
                  <Typography variant="body1">
                    {formatDateTime(updatedAt)}
                  </Typography>
                </Grid>
              )}
            </Grid>
          </Stack>
        </CardContent>
      </Card>

      {/* JSON Display */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Configuration Data
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            Full configuration schema (read-only)
          </Typography>
          <Paper
            sx={{
              maxHeight: 600,
              overflow: 'auto',
              p: 2,
              backgroundColor: '#1e1e1e',
              borderRadius: 1,
            }}
          >
            <SyntaxHighlighter
              language="json"
              style={vscDarkPlus}
              customStyle={{
                margin: 0,
                padding: 0,
                backgroundColor: 'transparent',
              }}
            >
              {jsonString}
            </SyntaxHighlighter>
          </Paper>
        </CardContent>
      </Card>

      {/* Diff Dialog */}
      {hasMultipleVersions && (
        <ConfigDiffDialog
          open={diffDialogOpen}
          onClose={() => setDiffDialogOpen(false)}
          type={type as UIConfigType}
          currentConfigId={id}
          availableVersions={availableVersions}
        />
      )}
    </Box>
  )
}

