/**
 * Tool Detail Page Component
 * 
 * Phase 8 P8-11: Tool detail page with metadata, schema viewer, config, status, executions, and execute button
 */

import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  Box,
  Button,
  Alert,
  Grid,
  Paper,
  Typography,
  Chip,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Stack,
  Divider,
} from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { BreadcrumbsNav } from '../components/common'
import PageHeader from '../components/common/PageHeader.tsx'
import CardSkeleton from '../components/common/CardSkeleton.tsx'
import { TableSkeleton } from '../components/common'
import { EmptyState } from '../components/common'
import { useTool, useToolExecutions } from '../hooks/useTools'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { formatDateTime } from '../utils/dateFormat'
import RunToolModal from '../components/tools/RunToolModal'

/**
 * Tool Detail Page Component
 */
export default function ToolDetailPage() {
  const { id } = useParams<{ id: string }>()
  const toolId = id ? parseInt(id, 10) : null

  const [executeDialogOpen, setExecuteDialogOpen] = useState(false)

  // Fetch tool detail
  const { data: tool, isLoading: isLoadingTool, isError: isErrorTool, error: toolError } = useTool(toolId)

  // Fetch recent executions (last 10)
  const { data: executionsData, isLoading: isLoadingExecutions } = useToolExecutions(
    toolId ? { tool_id: toolId, page: 1, page_size: 10 } : undefined
  )

  // Set document title
  useDocumentTitle(tool ? `Tool: ${tool.name}` : 'Tool Detail')

  // Get input/output schema from config
  const inputSchema = tool?.config?.inputSchema || tool?.config?.input_schema || null
  const outputSchema = tool?.config?.outputSchema || tool?.config?.output_schema || null
  const authType = tool?.config?.authType || tool?.config?.auth_type || 'none'
  const endpointConfig = tool?.config?.endpointConfig || tool?.config?.endpoint_config || null

  // Loading state
  if (isLoadingTool) {
    return (
      <Box>
        <BreadcrumbsNav
          items={[
            { label: 'Tools', to: '/tools' },
            { label: 'Loading...' },
          ]}
        />
        <PageHeader title="Tool Detail" subtitle="Loading tool information..." />
        <CardSkeleton lines={8} />
      </Box>
    )
  }

  // Error state
  if (isErrorTool || !tool) {
    return (
      <Box>
        <BreadcrumbsNav
          items={[
            { label: 'Tools', to: '/tools' },
            { label: 'Error' },
          ]}
        />
        <PageHeader title="Tool Not Found" subtitle="Unable to load tool details" />
        <Alert severity="error" sx={{ mt: 3 }}>
          {toolError?.message || 'Tool not found'}
        </Alert>
        <Button
          component={Link}
          to="/tools"
          sx={{ mt: 2 }}
          startIcon={<ArrowBackIcon />}
        >
          Back to Tools
        </Button>
      </Box>
    )
  }

  // Render status chip
  const renderStatusChip = (enabled: boolean | null) => {
    if (enabled === null) {
      return <Chip label="Unknown" size="small" color="default" variant="outlined" />
    }
    if (enabled) {
      return <Chip label="Enabled" size="small" color="success" />
    }
    return <Chip label="Disabled" size="small" color="error" />
  }

  // Render scope chip
  const renderScopeChip = (tenantId: string | null) => {
    if (tenantId === null) {
      return <Chip label="Global" size="small" color="primary" variant="outlined" />
    }
    return <Chip label="Tenant" size="small" color="secondary" variant="outlined" />
  }

  // Render execution status chip
  const renderExecutionStatusChip = (status: string) => {
    const colorMap: Record<string, 'success' | 'error' | 'warning' | 'default'> = {
      succeeded: 'success',
      failed: 'error',
      running: 'warning',
      requested: 'default',
    }
    return (
      <Chip
        label={status.charAt(0).toUpperCase() + status.slice(1)}
        size="small"
        color={colorMap[status] || 'default'}
      />
    )
  }

  return (
    <Box>
      <BreadcrumbsNav
        items={[
          { label: 'Tools', to: '/tools' },
          { label: tool.name },
        ]}
      />

      <PageHeader
        title={tool.name}
        subtitle={tool.config?.description || `Tool type: ${tool.type}`}
        actions={
          <Button
            variant="contained"
            startIcon={<PlayArrowIcon />}
            onClick={() => setExecuteDialogOpen(true)}
            disabled={tool.enabled === false}
          >
            Execute Tool
          </Button>
        }
      />

      <Grid container spacing={3}>
        {/* Left Column: Metadata and Config */}
        <Grid item xs={12} md={6}>
          {/* Tool Metadata */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Tool Metadata
              </Typography>
              <Divider sx={{ mb: 2 }} />
              <Stack spacing={2}>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Tool ID
                  </Typography>
                  <Typography variant="body1">{tool.toolId}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Type
                  </Typography>
                  <Typography variant="body1">
                    <Chip label={tool.type} size="small" variant="outlined" sx={{ ml: 1 }} />
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Scope
                  </Typography>
                  <Typography variant="body1" sx={{ mt: 0.5 }}>
                    {renderScopeChip(tool.tenantId)}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Status
                  </Typography>
                  <Typography variant="body1" sx={{ mt: 0.5 }}>
                    {renderStatusChip(tool.enabled)}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Created At
                  </Typography>
                  <Typography variant="body1">
                    {formatDateTime(tool.createdAt)}
                  </Typography>
                </Box>
                {tool.config?.description && (
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Description
                    </Typography>
                    <Typography variant="body1">{tool.config.description}</Typography>
                  </Box>
                )}
              </Stack>
            </CardContent>
          </Card>

          {/* Auth & Endpoint Config */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Authentication & Endpoint
              </Typography>
              <Divider sx={{ mb: 2 }} />
              <Stack spacing={2}>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Auth Type
                  </Typography>
                  <Typography variant="body1">
                    <Chip label={authType} size="small" variant="outlined" sx={{ ml: 1 }} />
                  </Typography>
                </Box>
                {endpointConfig && (
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Endpoint Configuration
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
                        {JSON.stringify(endpointConfig, null, 2)}
                      </SyntaxHighlighter>
                    </Paper>
                  </Box>
                )}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        {/* Right Column: Schemas */}
        <Grid item xs={12} md={6}>
          {/* Input Schema */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Input Schema
              </Typography>
              <Divider sx={{ mb: 2 }} />
              {inputSchema ? (
                <Paper
                  sx={{
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
                    {JSON.stringify(inputSchema, null, 2)}
                  </SyntaxHighlighter>
                </Paper>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No input schema defined
                </Typography>
              )}
            </CardContent>
          </Card>

          {/* Output Schema */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Output Schema
              </Typography>
              <Divider sx={{ mb: 2 }} />
              {outputSchema ? (
                <Paper
                  sx={{
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
                    {JSON.stringify(outputSchema, null, 2)}
                  </SyntaxHighlighter>
                </Paper>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No output schema defined
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Full Width: Recent Executions */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Executions
              </Typography>
              <Divider sx={{ mb: 2 }} />
              {isLoadingExecutions ? (
                <TableContainer>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Execution ID</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Actor</TableCell>
                        <TableCell>Created At</TableCell>
                        <TableCell>Updated At</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableSkeleton rowCount={5} columnCount={5} />
                  </Table>
                </TableContainer>
              ) : !executionsData || executionsData.items.length === 0 ? (
                <EmptyState
                  title="No executions found"
                  description="This tool has not been executed yet."
                />
              ) : (
                <TableContainer>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 600 }}>Execution ID</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Actor</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Exception ID</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Created At</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Updated At</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {executionsData.items.map((execution) => (
                        <TableRow key={execution.executionId} hover>
                          <TableCell>
                            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                              {execution.executionId.substring(0, 8)}...
                            </Typography>
                          </TableCell>
                          <TableCell>{renderExecutionStatusChip(execution.status)}</TableCell>
                          <TableCell>
                            <Typography variant="body2">
                              {execution.requestedByActorType}/{execution.requestedByActorId}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            {execution.exceptionId ? (
                              <Link
                                to={`/exceptions/${execution.exceptionId}`}
                                style={{ textDecoration: 'none' }}
                              >
                                <Typography
                                  variant="body2"
                                  color="primary"
                                  sx={{ fontFamily: 'monospace' }}
                                >
                                  {execution.exceptionId.substring(0, 8)}...
                                </Typography>
                              </Link>
                            ) : (
                              <Typography variant="body2" color="text.secondary">
                                —
                              </Typography>
                            )}
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">
                              {formatDateTime(execution.createdAt)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">
                              {formatDateTime(execution.updatedAt)}
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
        </Grid>
      </Grid>

      {/* Run Tool Modal */}
      <RunToolModal
        open={executeDialogOpen}
        onClose={() => setExecuteDialogOpen(false)}
        tool={tool}
      />

      {/* Back Button */}
      <Box sx={{ mt: 3 }}>
        <Button
          component={Link}
          to="/tools"
          startIcon={<ArrowBackIcon />}
        >
          Back to Tools
        </Button>
      </Box>
    </Box>
  )
}

