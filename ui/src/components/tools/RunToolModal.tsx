/**
 * Run Tool Modal Component
 * 
 * Phase 8 P8-12: Enhanced tool execution modal with validation, status display, and output viewer
 */

import { useState, useEffect } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Stack,
  Alert,
  Typography,
  Paper,
  Box,
  Chip,
  Tabs,
  Tab,
  Divider,
  CircularProgress,
} from '@mui/material'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import ErrorIcon from '@mui/icons-material/Error'
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import { useExecuteTool } from '../../hooks/useTools'
import { useSnackbar } from '../common/SnackbarProvider'
import type { ToolDefinition, ToolExecution } from '../../api/tools'

/**
 * Basic JSON schema validation
 * Validates payload against input schema structure
 */
function validatePayloadAgainstSchema(payload: any, schema: any): { valid: boolean; errors: string[] } {
  const errors: string[] = []

  if (!schema || typeof schema !== 'object') {
    return { valid: true, errors: [] } // No schema to validate against
  }

  // Check required fields
  if (schema.required && Array.isArray(schema.required)) {
    for (const field of schema.required) {
      if (!(field in payload)) {
        errors.push(`Missing required field: ${field}`)
      }
    }
  }

  // Check properties
  if (schema.properties && typeof schema.properties === 'object') {
    for (const [key, propSchema] of Object.entries(schema.properties)) {
      const propValue = payload[key]
      const propDef = propSchema as any

      // If property exists, check its type
      if (propValue !== undefined && propDef.type) {
        const expectedType = propDef.type
        const actualType = typeof propValue

        // Type checking
        if (expectedType === 'string' && actualType !== 'string') {
          errors.push(`Field '${key}' should be a string, got ${actualType}`)
        } else if (expectedType === 'number' && actualType !== 'number') {
          errors.push(`Field '${key}' should be a number, got ${actualType}`)
        } else if (expectedType === 'boolean' && actualType !== 'boolean') {
          errors.push(`Field '${key}' should be a boolean, got ${actualType}`)
        } else if (expectedType === 'object' && (actualType !== 'object' || Array.isArray(propValue))) {
          errors.push(`Field '${key}' should be an object, got ${actualType}`)
        } else if (expectedType === 'array' && !Array.isArray(propValue)) {
          errors.push(`Field '${key}' should be an array, got ${actualType}`)
        }
      }
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  }
}

interface RunToolModalProps {
  open: boolean
  onClose: () => void
  tool: ToolDefinition | null
}

/**
 * Tab panel component
 */
interface TabPanelProps {
  children?: React.ReactNode
  index: number
  value: number
}

function TabPanel({ children, value, index }: TabPanelProps) {
  return (
    <div role="tabpanel" hidden={value !== index} id={`run-tool-tabpanel-${index}`}>
      {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
    </div>
  )
}

/**
 * Run Tool Modal Component
 */
export default function RunToolModal({ open, onClose, tool }: RunToolModalProps) {
  const { showSuccess, showError } = useSnackbar()
  const executeMutation = useExecuteTool()

  const [actorId, setActorId] = useState('user-001')
  const [payload, setPayload] = useState('{}')
  const [validationResult, setValidationResult] = useState<{ valid: boolean; errors: string[] } | null>(null)
  const [executionResult, setExecutionResult] = useState<ToolExecution | null>(null)
  const [activeTab, setActiveTab] = useState(0)

  // Get input schema from tool config
  const inputSchema = tool?.config?.inputSchema || tool?.config?.input_schema || null

  // Reset state when modal opens/closes
  useEffect(() => {
    if (open) {
      setPayload('{}')
      setActorId('user-001')
      setValidationResult(null)
      setExecutionResult(null)
      setActiveTab(0)
    }
  }, [open])

  // Parse payload JSON
  const parsePayload = (): { success: boolean; data?: any; error?: string } => {
    try {
      const parsed = JSON.parse(payload)
      return { success: true, data: parsed }
    } catch (error: any) {
      return { success: false, error: error.message || 'Invalid JSON' }
    }
  }

  // Validate payload against schema
  const handleValidate = () => {
    const parseResult = parsePayload()
    if (!parseResult.success) {
      setValidationResult({ valid: false, errors: [parseResult.error || 'Invalid JSON'] })
      return
    }

    if (!inputSchema) {
      setValidationResult({ valid: true, errors: [] })
      showSuccess('Payload is valid JSON (no schema to validate against)')
      return
    }

    const validation = validatePayloadAgainstSchema(parseResult.data, inputSchema)
    setValidationResult(validation)

    if (validation.valid) {
      showSuccess('Payload is valid against the input schema')
    } else {
      showError(`Validation failed: ${validation.errors.join(', ')}`)
    }
  }

  // Execute tool
  const handleExecute = async () => {
    if (!tool) return

    const parseResult = parsePayload()
    if (!parseResult.success) {
      showError(`Invalid JSON: ${parseResult.error}`)
      return
    }

    try {
      const result = await executeMutation.mutateAsync({
        toolId: tool.toolId,
        request: {
          payload: parseResult.data,
          actorId: actorId.trim(),
          actorType: 'user',
        },
      })

      setExecutionResult(result)
      setActiveTab(1) // Switch to results tab
      showSuccess('Tool executed successfully')
    } catch (error: any) {
      showError(error.message || 'Failed to execute tool')
      // Still set execution result if we got a response
      if (error.response?.data) {
        setExecutionResult(error.response.data)
        setActiveTab(1)
      }
    }
  }

  // Check if payload is valid JSON
  const isPayloadValidJSON = (() => {
    try {
      JSON.parse(payload)
      return true
    } catch {
      return false
    }
  })()

  // Render execution status chip
  const renderStatusChip = (status: string) => {
    const statusConfig: Record<string, { label: string; color: 'success' | 'error' | 'warning' | 'default' | 'info'; icon: React.ReactNode }> = {
      succeeded: {
        label: 'Succeeded',
        color: 'success',
        icon: <CheckCircleIcon sx={{ fontSize: 16, mr: 0.5 }} />,
      },
      failed: {
        label: 'Failed',
        color: 'error',
        icon: <ErrorIcon sx={{ fontSize: 16, mr: 0.5 }} />,
      },
      running: {
        label: 'Running',
        color: 'warning',
        icon: <HourglassEmptyIcon sx={{ fontSize: 16, mr: 0.5 }} />,
      },
      requested: {
        label: 'Requested',
        color: 'info',
        icon: <HourglassEmptyIcon sx={{ fontSize: 16, mr: 0.5 }} />,
      },
    }

    const config = statusConfig[status] || { label: status, color: 'default' as const, icon: null }
    return (
      <Chip
        label={config.label}
        color={config.color}
        size="small"
        icon={config.icon || undefined}
        sx={{ fontWeight: 500 }}
      />
    )
  }

  if (!tool) return null

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>
        <Stack direction="row" spacing={2} alignItems="center">
          <PlayArrowIcon color="primary" />
          <Typography variant="h6">Execute Tool: {tool.name}</Typography>
        </Stack>
      </DialogTitle>
      <DialogContent>
        <Tabs value={activeTab} onChange={(_, newValue) => setActiveTab(newValue)} sx={{ mb: 2 }}>
          <Tab label="Input" />
          <Tab label="Results" disabled={!executionResult} />
        </Tabs>

        {/* Input Tab */}
        <TabPanel value={activeTab} index={0}>
          <Stack spacing={3}>
            <TextField
              label="Actor ID"
              value={actorId}
              onChange={(e) => setActorId(e.target.value)}
              fullWidth
              required
              helperText="Identifier for the user/agent executing this tool"
            />

            <TextField
              label="Payload (JSON)"
              value={payload}
              onChange={(e) => {
                setPayload(e.target.value)
                setValidationResult(null) // Clear validation when payload changes
              }}
              fullWidth
              multiline
              rows={12}
              required
              helperText="Input payload matching the tool's input schema"
              error={!isPayloadValidJSON}
              sx={{
                '& .MuiInputBase-input': {
                  fontFamily: 'monospace',
                  fontSize: '0.875rem',
                },
              }}
            />

            {/* Validation Result */}
            {validationResult && (
              <Alert
                severity={validationResult.valid ? 'success' : 'error'}
                sx={{ mt: 1 }}
              >
                <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 0.5 }}>
                  {validationResult.valid ? 'Validation Passed' : 'Validation Failed'}
                </Typography>
                {validationResult.errors.length > 0 && (
                  <Box component="ul" sx={{ m: 0, pl: 2 }}>
                    {validationResult.errors.map((error, idx) => (
                      <li key={idx}>
                        <Typography variant="body2">{error}</Typography>
                      </li>
                    ))}
                  </Box>
                )}
              </Alert>
            )}

            {/* Input Schema Reference */}
            {inputSchema && (
              <Alert severity="info">
                <Typography variant="caption" component="div" sx={{ fontWeight: 600, mb: 0.5 }}>
                  Expected Input Schema:
                </Typography>
                <Paper
                  sx={{
                    mt: 1,
                    p: 1.5,
                    bgcolor: 'grey.900',
                    maxHeight: 200,
                    overflow: 'auto',
                  }}
                >
                  <SyntaxHighlighter
                    language="json"
                    style={vscDarkPlus}
                    customStyle={{ margin: 0, fontSize: '0.75rem' }}
                  >
                    {JSON.stringify(inputSchema, null, 2)}
                  </SyntaxHighlighter>
                </Paper>
              </Alert>
            )}
          </Stack>
        </TabPanel>

        {/* Results Tab */}
        <TabPanel value={activeTab} index={1}>
          {executionResult ? (
            <Stack spacing={3}>
              {/* Execution Status */}
              <Box>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Execution Status
                </Typography>
                <Box sx={{ mt: 1 }}>
                  {renderStatusChip(executionResult.status)}
                </Box>
              </Box>

              <Divider />

              {/* Execution Details */}
              <Box>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Execution Details
                </Typography>
                <Stack spacing={1} sx={{ mt: 1 }}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Execution ID
                    </Typography>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {executionResult.executionId}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Actor
                    </Typography>
                    <Typography variant="body2">
                      {executionResult.requestedByActorType}/{executionResult.requestedByActorId}
                    </Typography>
                  </Box>
                  {executionResult.exceptionId && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Exception ID
                      </Typography>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {executionResult.exceptionId}
                      </Typography>
                    </Box>
                  )}
                  {executionResult.errorMessage && (
                    <Alert severity="error" sx={{ mt: 1 }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 0.5 }}>
                        Error Message
                      </Typography>
                      <Typography variant="body2">{executionResult.errorMessage}</Typography>
                    </Alert>
                  )}
                </Stack>
              </Box>

              <Divider />

              {/* Input Payload */}
              <Box>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Input Payload
                </Typography>
                <Paper
                  sx={{
                    mt: 1,
                    p: 2,
                    bgcolor: 'grey.900',
                    maxHeight: 300,
                    overflow: 'auto',
                  }}
                >
                  <SyntaxHighlighter
                    language="json"
                    style={vscDarkPlus}
                    customStyle={{ margin: 0, fontSize: '0.875rem' }}
                  >
                    {JSON.stringify(executionResult.inputPayload, null, 2)}
                  </SyntaxHighlighter>
                </Paper>
              </Box>

              {/* Output Payload */}
              {executionResult.outputPayload && (
                <Box>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Output Payload
                  </Typography>
                  <Paper
                    sx={{
                      mt: 1,
                      p: 2,
                      bgcolor: 'grey.900',
                      maxHeight: 400,
                      overflow: 'auto',
                    }}
                  >
                    <SyntaxHighlighter
                      language="json"
                      style={vscDarkPlus}
                      customStyle={{ margin: 0, fontSize: '0.875rem' }}
                    >
                      {JSON.stringify(executionResult.outputPayload, null, 2)}
                    </SyntaxHighlighter>
                  </Paper>
                </Box>
              )}

              {!executionResult.outputPayload && executionResult.status === 'succeeded' && (
                <Alert severity="info">
                  No output payload available for this execution.
                </Alert>
              )}
            </Stack>
          ) : (
            <Alert severity="info">No execution results yet. Execute the tool to see results here.</Alert>
          )}
        </TabPanel>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{executionResult ? 'Close' : 'Cancel'}</Button>
        {activeTab === 0 && (
          <>
            <Button
              onClick={handleValidate}
              variant="outlined"
              disabled={!isPayloadValidJSON || !inputSchema}
            >
              Validate
            </Button>
            <Button
              onClick={handleExecute}
              variant="contained"
              startIcon={executeMutation.isPending ? <CircularProgress size={16} /> : <PlayArrowIcon />}
              disabled={
                executeMutation.isPending ||
                !actorId.trim() ||
                !isPayloadValidJSON ||
                (validationResult !== null && !validationResult.valid)
              }
            >
              {executeMutation.isPending ? 'Executing...' : 'Execute'}
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  )
}

