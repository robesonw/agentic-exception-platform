import { useState, useEffect } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Box,
  Stack,
  Chip,
  Alert,
  CircularProgress,
  Typography,
  Divider,
} from '@mui/material'
import { useMutation } from '@tanstack/react-query'
import ReactDiffViewer from 'react-diff-viewer-continued'
import { getConfigDiff } from '../../api/config.ts'
import type { ConfigDiffResponse, ConfigHistoryItem } from '../../types'
import { useSnackbar } from '../common/SnackbarProvider.tsx'

/**
 * UI config type (with hyphens and plural)
 */
export type UIConfigType = 'domain-packs' | 'tenant-policies' | 'playbooks'

/**
 * Map UI config type to backend config type
 */
function mapUIConfigTypeToBackend(uiType: UIConfigType): 'domain_pack' | 'tenant_policy' | 'playbook' {
  switch (uiType) {
    case 'domain-packs':
      return 'domain_pack'
    case 'tenant-policies':
      return 'tenant_policy'
    case 'playbooks':
      return 'playbook'
    default:
      throw new Error(`Unknown UI config type: ${uiType}`)
  }
}

/**
 * Format version label for display
 */
function formatVersionLabel(item: ConfigHistoryItem): string {
  if (item.timestamp) {
    try {
      const date = new Date(item.timestamp)
      return `v${item.version} (${date.toLocaleDateString()})`
    } catch {
      return `v${item.version}`
    }
  }
  return `v${item.version}`
}

/**
 * Props for ConfigDiffDialog component
 */
export interface ConfigDiffDialogProps {
  /** Whether dialog is open */
  open: boolean
  /** Callback when dialog closes */
  onClose: () => void
  /** Configuration type (UI format) */
  type: UIConfigType
  /** Current configuration ID */
  currentConfigId: string
  /** Available versions for comparison */
  availableVersions: ConfigHistoryItem[]
}

/**
 * Config Diff Dialog Component
 * 
 * Allows users to compare two versions of a configuration.
 * Shows side-by-side diff with color highlighting.
 */
export default function ConfigDiffDialog({
  open,
  onClose,
  type,
  currentConfigId,
  availableVersions,
}: ConfigDiffDialogProps) {
  const { showError } = useSnackbar()
  const [leftVersionId, setLeftVersionId] = useState<string>('')
  const [rightVersionId, setRightVersionId] = useState<string>('')

  // Initialize versions: left = previous, right = current
  useEffect(() => {
    if (open && availableVersions.length > 0) {
      // Find current version index
      const currentIndex = availableVersions.findIndex((v) => v.id === currentConfigId)
      
      if (currentIndex > 0) {
        // Set left to previous version
        setLeftVersionId(availableVersions[currentIndex - 1].id)
      } else if (availableVersions.length > 1) {
        // If current is first, use first as left
        setLeftVersionId(availableVersions[0].id)
      } else {
        setLeftVersionId(availableVersions[0].id)
      }
      
      // Set right to current version
      setRightVersionId(currentConfigId)
    }
  }, [open, availableVersions, currentConfigId])

  // Mutation for fetching diff
  const diffMutation = useMutation({
    mutationFn: async (params: { leftVersion: string; rightVersion: string }) => {
      return getConfigDiff({
        type: mapUIConfigTypeToBackend(type),
        leftVersion: params.leftVersion,
        rightVersion: params.rightVersion,
      })
    },
    onError: (error: Error) => {
      showError(`Failed to load diff: ${error.message}`)
    },
  })

  // Handle diff fetch
  const handleCompare = () => {
    if (!leftVersionId || !rightVersionId) {
      showError('Please select both versions to compare')
      return
    }
    if (leftVersionId === rightVersionId) {
      showError('Please select different versions to compare')
      return
    }
    diffMutation.mutate({
      leftVersion: leftVersionId,
      rightVersion: rightVersionId,
    })
  }

  // Get version labels
  const leftVersion = availableVersions.find((v) => v.id === leftVersionId)
  const rightVersion = availableVersions.find((v) => v.id === rightVersionId)
  const leftLabel = leftVersion ? formatVersionLabel(leftVersion) : ''
  const rightLabel = rightVersion ? formatVersionLabel(rightVersion) : ''

  // Calculate summary from diff response
  const diffData: ConfigDiffResponse | undefined = diffMutation.data
  let additions = 0
  let deletions = 0
  let changes = 0

  if (diffData?.summary) {
    // Try to extract counts from summary (backend-dependent structure)
    const summary = diffData.summary
    additions = (summary.additions as number) || (summary.added as number) || 0
    deletions = (summary.deletions as number) || (summary.removed as number) || 0
    changes = (summary.changes as number) || (summary.modified as number) || 0
  }

  // Format JSON strings for diff viewer
  const leftJson = diffData?.left ? JSON.stringify(diffData.left, null, 2) : ''
  const rightJson = diffData?.right ? JSON.stringify(diffData.right, null, 2) : ''

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>Compare Configuration Versions</DialogTitle>
      <DialogContent>
        <Stack spacing={3}>
          {/* Version Selectors */}
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <FormControl sx={{ minWidth: 200 }} size="small">
              <InputLabel>Left Version</InputLabel>
              <Select
                value={leftVersionId}
                onChange={(e) => setLeftVersionId(e.target.value)}
                label="Left Version"
              >
                {availableVersions.map((version) => (
                  <MenuItem key={version.id} value={version.id}>
                    {formatVersionLabel(version)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl sx={{ minWidth: 200 }} size="small">
              <InputLabel>Right Version</InputLabel>
              <Select
                value={rightVersionId}
                onChange={(e) => setRightVersionId(e.target.value)}
                label="Right Version"
              >
                {availableVersions.map((version) => (
                  <MenuItem key={version.id} value={version.id}>
                    {formatVersionLabel(version)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Button
              variant="contained"
              onClick={handleCompare}
              disabled={!leftVersionId || !rightVersionId || leftVersionId === rightVersionId || diffMutation.isPending}
            >
              Compare
            </Button>
          </Box>

          {/* Summary Badges (shown after diff is loaded) */}
          {diffData && (
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Chip
                label={`${additions} additions`}
                color="success"
                size="small"
              />
              <Chip
                label={`${deletions} deletions`}
                color="error"
                size="small"
              />
              <Chip
                label={`${changes} changes`}
                color="warning"
                size="small"
              />
            </Box>
          )}

          <Divider />

          {/* Error State */}
          {diffMutation.isError && (
            <Alert severity="error">
              Failed to load diff: {diffMutation.error?.message || 'Unknown error'}
            </Alert>
          )}

          {/* Loading State */}
          {diffMutation.isPending && (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          )}

          {/* Diff Viewer */}
          {diffData && !diffMutation.isPending && (
            <Box>
              <Typography variant="subtitle2" gutterBottom>
                Comparing {leftLabel} vs {rightLabel}
              </Typography>
              <Box
                sx={{
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  overflow: 'hidden',
                  maxHeight: 600,
                  overflowY: 'auto',
                }}
              >
                <ReactDiffViewer
                  oldValue={leftJson}
                  newValue={rightJson}
                  splitView={true}
                  leftTitle={leftLabel}
                  rightTitle={rightLabel}
                  showDiffOnly={false}
                  useDarkTheme={true}
                />
              </Box>
            </Box>
          )}

          {/* Empty State (no diff loaded yet) */}
          {!diffData && !diffMutation.isPending && !diffMutation.isError && (
            <Alert severity="info">
              Select two versions and click "Compare" to view differences.
            </Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  )
}

