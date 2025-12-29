import React, { useState, useMemo } from 'react'
import {
  Box,
  Tabs,
  Tab,
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
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Button,
  Alert,
  Stack,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tooltip,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import AccountTreeIcon from '@mui/icons-material/AccountTree'
import CodeViewer from '../common/CodeViewer'
import { formatDateTime } from '../../utils/dateFormat'
import type { Pack } from '../../api/onboarding'
import WorkflowViewer from '../exceptions/WorkflowViewer'
import { WorkflowNode, WorkflowEdge } from '../../types/exceptions'

interface TabPanelProps {
  children?: React.ReactNode
  index: number
  value: number
}

function TabPanel({ children, value, index, ...other }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`pack-content-tabpanel-${index}`}
      aria-labelledby={`pack-content-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  )
}

interface PackContentViewerProps {
  pack: Pack
  packType: 'domain' | 'tenant'
}

interface PlaybookStep {
  id: string
  name?: string
  type?: string
  tool?: string | Record<string, unknown>
  tool_id?: string
  tool_ref?: string
  conditions?: Record<string, unknown>
  approval_required?: boolean
  approval?: {
    required?: boolean
    type?: string
    level?: string
  }
  metadata?: Record<string, unknown>
  next_step_id?: string
  on_success?: string
  on_failure?: string
}

interface Playbook {
  id: string
  playbook_id?: string
  name?: string
  description?: string
  version?: string
  match_rules?: Record<string, unknown>
  applicable_conditions?: Record<string, unknown>
  classifiers?: string[]
  default?: boolean
  fallback?: boolean
  steps?: PlaybookStep[]
  metadata?: Record<string, unknown>
}

interface ToolDefinition {
  id: string
  name?: string
  type?: string
  description?: string
  parameters?: Record<string, unknown>
  metadata?: Record<string, unknown>
}

interface PolicyClause {
  id: string
  name?: string
  description?: string
  rules?: Record<string, unknown>
  enforcement?: string
  metadata?: Record<string, unknown>
}

export default function PackContentViewer({ pack, packType }: PackContentViewerProps) {
  const [selectedTab, setSelectedTab] = useState(0)
  const [selectedPlaybook, setSelectedPlaybook] = useState<Playbook | null>(null)
  const [diagramModalOpen, setDiagramModalOpen] = useState(false)

  // Parse pack content to extract structured data
  const parsedContent = useMemo(() => {
    if (!pack.content_json) return null
    
    try {
      const content = typeof pack.content_json === 'string' 
        ? JSON.parse(pack.content_json) 
        : pack.content_json

      const playbooks: Playbook[] = []
      const tools: ToolDefinition[] = []
      const policies: PolicyClause[] = []

      // Extract playbooks
      if (content.playbooks && Array.isArray(content.playbooks)) {
        playbooks.push(...content.playbooks)
      }

      // Extract tools 
      if (content.tools && Array.isArray(content.tools)) {
        tools.push(...content.tools)
      }

      // Extract policies
      if (content.policies && Array.isArray(content.policies)) {
        policies.push(...content.policies)
      }

      // For tenant packs, also check policy_rules
      if (packType === 'tenant' && content.policy_rules && Array.isArray(content.policy_rules)) {
        policies.push(...content.policy_rules)
      }

      return {
        raw: content,
        playbooks,
        tools,
        policies,
        metadata: content.metadata || {},
        version: content.version || pack.version,
        domain: content.domain || content.domainName || pack.domain,
        description: content.description,
      }
    } catch (error) {
      console.error('Failed to parse pack content:', error)
      return null
    }
  }, [pack.content_json, packType, pack.version, pack.domain])

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setSelectedTab(newValue)
  }

  // Redact sensitive fields from tools
  const redactToolSecrets = (tool: ToolDefinition): ToolDefinition => {
    const redacted = { ...tool }
    if (redacted.parameters) {
      const params = { ...redacted.parameters }
      // Redact common secret field names
      const secretFields = ['password', 'secret', 'key', 'token', 'credential', 'auth']
      Object.keys(params).forEach(paramKey => {
        const value = params[paramKey]
        if (typeof value === 'string' && secretFields.some(field => paramKey.toLowerCase().includes(field))) {
          params[paramKey] = '***REDACTED***'
        }
        // Also check for connection strings and URLs with credentials
        if (typeof value === 'string' && (value.includes('password=') || value.includes('://') && value.includes('@'))) {
          // Redact database connection strings and URLs with embedded credentials
          params[paramKey] = value.replace(/password=[^;&\s]+/gi, 'password=***REDACTED***')
                                 .replace(/:\/\/[^:@]+:[^@]+@/, '://***REDACTED***:***REDACTED***@')
        }
      })
      redacted.parameters = params
    }
    return redacted
  }

  // Convert playbook steps to workflow diagram nodes and edges
  const convertPlaybookToWorkflow = (playbook: Playbook): { nodes: WorkflowNode[], edges: WorkflowEdge[] } => {
    if (!playbook.steps || playbook.steps.length === 0) {
      return { nodes: [], edges: [] }
    }

    const nodes: WorkflowNode[] = []
    const edges: WorkflowEdge[] = []

    playbook.steps.forEach((step, index) => {
      const stepId = step.id || `step-${index}`
      
      // Extract tool reference
      let toolRef = ''
      if (typeof step.tool === 'string') {
        toolRef = step.tool
      } else if (step.tool_id) {
        toolRef = step.tool_id
      } else if (step.tool_ref) {
        toolRef = step.tool_ref
      } else if (step.tool && typeof step.tool === 'object' && 'id' in step.tool && typeof step.tool.id === 'string') {
        toolRef = step.tool.id
      }

      nodes.push({
        id: stepId,
        type: step.type || 'unknown',
        kind: 'step',
        label: step.name || stepId,
        status: 'pending', // Definition view - no execution status
        started_at: null,
        completed_at: null,
        meta: {
          step_index: index,
          tool: toolRef,
          approval_required: step.approval_required || step.approval?.required || false,
          conditions: step.conditions || {}
        }
      })

      // Create edges based on step order and transitions
      if (playbook.steps && index < playbook.steps.length - 1) {
        const nextStepId = playbook.steps[index + 1].id || `step-${index + 1}`
        edges.push({
          id: `${stepId}-to-${nextStepId}`,
          source: stepId,
          target: nextStepId,
          label: null
        })
      }

      // Add conditional edges if specified
      if (step.on_success && step.on_success !== stepId) {
        edges.push({
          id: `${stepId}-success`,
          source: stepId,
          target: step.on_success,
          label: 'Success'
        })
      }

      if (step.on_failure && step.on_failure !== stepId) {
        edges.push({
          id: `${stepId}-failure`,
          source: stepId,
          target: step.on_failure,
          label: 'Failure'
        })
      }
    })

    return { nodes, edges }
  }

  if (!parsedContent) {
    return (
      <Alert severity="error">
        Failed to parse pack content. The JSON structure may be invalid.
      </Alert>
    )
  }

  return (
    <Box sx={{ width: '100%' }}>
      <Tabs value={selectedTab} onChange={handleTabChange} aria-label="pack content tabs">
        <Tab label="Overview" />
        <Tab label="Raw JSON" />
        <Tab label={`Playbooks (${parsedContent.playbooks.length})`} />
        <Tab label={`Tools (${parsedContent.tools.length})`} />
        <Tab label={`Policies (${parsedContent.policies.length})`} />
      </Tabs>

      {/* Overview Tab */}
      <TabPanel value={selectedTab} index={0}>
        <Stack spacing={3}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Pack Information
              </Typography>
              <Stack direction="row" spacing={4} sx={{ mb: 2 }}>
                <Box>
                  <Typography variant="subtitle2" color="text.secondary">Version</Typography>
                  <Typography variant="body1">{pack.version}</Typography>
                </Box>
                <Box>
                  <Typography variant="subtitle2" color="text.secondary">Status</Typography>
                  <Chip 
                    label={pack.status} 
                    size="small"
                    color={pack.status === 'ACTIVE' ? 'success' : pack.status === 'DEPRECATED' ? 'error' : 'default'}
                  />
                </Box>
                {pack.domain && (
                  <Box>
                    <Typography variant="subtitle2" color="text.secondary">Domain</Typography>
                    <Typography variant="body1">{pack.domain}</Typography>
                  </Box>
                )}
                {pack.tenant_id && (
                  <Box>
                    <Typography variant="subtitle2" color="text.secondary">Tenant ID</Typography>
                    <Typography variant="body1">{pack.tenant_id}</Typography>
                  </Box>
                )}
              </Stack>
              <Stack direction="row" spacing={4}>
                <Box>
                  <Typography variant="subtitle2" color="text.secondary">Created</Typography>
                  <Typography variant="body1">{formatDateTime(pack.created_at)}</Typography>
                </Box>
                <Box>
                  <Typography variant="subtitle2" color="text.secondary">Created By</Typography>
                  <Typography variant="body1">{pack.created_by || 'Unknown'}</Typography>
                </Box>
                <Box>
                  <Typography variant="subtitle2" color="text.secondary">Checksum</Typography>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                    {pack.checksum?.substring(0, 16)}...
                  </Typography>
                </Box>
              </Stack>
              {parsedContent.description && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" color="text.secondary">Description</Typography>
                  <Typography variant="body2">{parsedContent.description}</Typography>
                </Box>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Content Summary
              </Typography>
              <Stack direction="row" spacing={4}>
                <Box>
                  <Typography variant="h4" color="primary">{parsedContent.playbooks.length}</Typography>
                  <Typography variant="body2" color="text.secondary">Playbooks</Typography>
                </Box>
                <Box>
                  <Typography variant="h4" color="primary">{parsedContent.tools.length}</Typography>
                  <Typography variant="body2" color="text.secondary">Tools</Typography>
                </Box>
                <Box>
                  <Typography variant="h4" color="primary">{parsedContent.policies.length}</Typography>
                  <Typography variant="body2" color="text.secondary">Policies</Typography>
                </Box>
              </Stack>
            </CardContent>
          </Card>
        </Stack>
      </TabPanel>

      {/* Raw JSON Tab */}
      <TabPanel value={selectedTab} index={1}>
        <CodeViewer
          code={JSON.stringify(parsedContent.raw, null, 2)}
          language="json"
          title="Complete Pack Configuration"
          maxHeight={600}
        />
      </TabPanel>

      {/* Playbooks Tab */}
      <TabPanel value={selectedTab} index={2}>
        {parsedContent.playbooks.length === 0 ? (
          <Alert severity="info">No playbooks defined in this pack.</Alert>
        ) : (
          <Stack spacing={2}>
            {!selectedPlaybook ? (
              // Playbook list
              <>
                <Typography variant="h6" gutterBottom>
                  Playbooks ({parsedContent.playbooks.length})
                </Typography>
                <TableContainer component={Paper}>
                  <Table>
                    <TableHead>
                      <TableRow key="playbooks-header">
                        <TableCell>ID</TableCell>
                        <TableCell>Name</TableCell>
                        <TableCell>Description</TableCell>
                        <TableCell>Version</TableCell>
                        <TableCell>Steps</TableCell>
                        <TableCell>Type</TableCell>
                        <TableCell>Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {parsedContent.playbooks.map((playbook) => (
                        <TableRow key={playbook.playbook_id || playbook.id}>
                          <TableCell sx={{ fontFamily: 'monospace' }}>
                            {playbook.playbook_id || playbook.id}
                          </TableCell>
                          <TableCell>{playbook.name || '-'}</TableCell>
                          <TableCell>
                            <Typography variant="body2" sx={{ maxWidth: 300 }}>
                              {playbook.description ? 
                                (playbook.description.length > 100 ? 
                                  `${playbook.description.substring(0, 100)}...` : 
                                  playbook.description) 
                                : '-'}
                            </Typography>
                          </TableCell>
                          <TableCell>{playbook.version || '-'}</TableCell>
                          <TableCell>{playbook.steps?.length || 0}</TableCell>
                          <TableCell>
                            <Stack direction="row" spacing={0.5}>
                              {playbook.default && (
                                <Chip label="Default" size="small" color="primary" />
                              )}
                              {playbook.fallback && (
                                <Chip label="Fallback" size="small" color="secondary" />
                              )}
                              {!playbook.default && !playbook.fallback && (
                                <Typography variant="body2" color="text.secondary">Standard</Typography>
                              )}
                            </Stack>
                          </TableCell>
                          <TableCell>
                            <Button 
                              size="small"
                              onClick={() => setSelectedPlaybook(playbook)}
                            >
                              View Details
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </>
            ) : (
              // Playbook detail view
              <Stack spacing={3}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="h6">
                    Playbook: {selectedPlaybook.name || selectedPlaybook.id}
                  </Typography>
                  <Button 
                    variant="outlined" 
                    onClick={() => setSelectedPlaybook(null)}
                  >
                    Back to List
                  </Button>
                </Box>

                <Card>
                  <CardContent>
                    <Typography variant="subtitle1" gutterBottom>
                      Playbook Information
                    </Typography>
                    <Stack spacing={2}>
                      <Stack direction="row" spacing={4}>
                        <Box>
                          <Typography variant="subtitle2" color="text.secondary">Playbook ID</Typography>
                          <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                            {selectedPlaybook.playbook_id || selectedPlaybook.id}
                          </Typography>
                        </Box>
                        {selectedPlaybook.version && (
                          <Box>
                            <Typography variant="subtitle2" color="text.secondary">Version</Typography>
                            <Typography variant="body2">{selectedPlaybook.version}</Typography>
                          </Box>
                        )}
                        {(selectedPlaybook.default || selectedPlaybook.fallback) && (
                          <Box>
                            <Typography variant="subtitle2" color="text.secondary">Type</Typography>
                            <Stack direction="row" spacing={1}>
                              {selectedPlaybook.default && (
                                <Chip label="Default" size="small" color="primary" />
                              )}
                              {selectedPlaybook.fallback && (
                                <Chip label="Fallback" size="small" color="secondary" />
                              )}
                            </Stack>
                          </Box>
                        )}
                      </Stack>
                      
                      {selectedPlaybook.name && (
                        <Box>
                          <Typography variant="subtitle2" color="text.secondary">Name</Typography>
                          <Typography variant="body1">{selectedPlaybook.name}</Typography>
                        </Box>
                      )}
                      
                      {selectedPlaybook.description && (
                        <Box>
                          <Typography variant="subtitle2" color="text.secondary">Description</Typography>
                          <Typography variant="body2">{selectedPlaybook.description}</Typography>
                        </Box>
                      )}
                      
                      {(selectedPlaybook.applicable_conditions || selectedPlaybook.classifiers) && (
                        <Box>
                          <Typography variant="subtitle2" color="text.secondary">Applicable Conditions</Typography>
                          <Box sx={{ mt: 1 }}>
                            {selectedPlaybook.classifiers && selectedPlaybook.classifiers.length > 0 && (
                              <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
                                <Typography variant="body2" color="text.secondary">Classifiers:</Typography>
                                {selectedPlaybook.classifiers.map((classifier, idx) => (
                                  <Chip key={`classifier-${idx}-${classifier}`} label={classifier} size="small" variant="outlined" />
                                ))}
                              </Stack>
                            )}
                            {selectedPlaybook.applicable_conditions && (
                              <CodeViewer
                                code={JSON.stringify(selectedPlaybook.applicable_conditions, null, 2)}
                                language="json"
                                maxHeight={200}
                              />
                            )}
                          </Box>
                        </Box>
                      )}
                    </Stack>
                  </CardContent>
                </Card>

                {selectedPlaybook.match_rules && (
                  <Accordion>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="subtitle1">Match Rules</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <CodeViewer
                        code={JSON.stringify(selectedPlaybook.match_rules, null, 2)}
                        language="json"
                        maxHeight={300}
                      />
                    </AccordionDetails>
                  </Accordion>
                )}

                {selectedPlaybook.steps && selectedPlaybook.steps.length > 0 && (
                  <Card>
                    <CardContent>
                      <Typography variant="subtitle1" gutterBottom>
                        Execution Steps ({selectedPlaybook.steps.length})
                      </Typography>
                      <TableContainer>
                        <Table size="small">
                          <TableHead>
                            <TableRow key="steps-header">
                              <TableCell>Step ID</TableCell>
                              <TableCell>Name</TableCell>
                              <TableCell>Type</TableCell>
                              <TableCell>Tool</TableCell>
                              <TableCell>Approval</TableCell>
                              <TableCell>Conditions</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {selectedPlaybook.steps.map((step, index) => {
                              const stepId = step.id || `step-${index}`
                              const stepName = step.name || `Step ${index + 1}`
                              const stepType = step.type || 'unknown'
                              
                              // Extract tool reference
                              let toolRef = '-'
                              if (typeof step.tool === 'string') {
                                toolRef = step.tool
                              } else if (step.tool_id) {
                                toolRef = step.tool_id
                              } else if (step.tool_ref) {
                                toolRef = step.tool_ref
                              } else if (step.tool && typeof step.tool === 'object' && 'id' in step.tool && typeof step.tool.id === 'string') {
                                toolRef = step.tool.id
                              }
                              
                              // Extract approval info
                              let approvalRequired = false
                              let approvalType = ''
                              if (step.approval_required !== undefined) {
                                approvalRequired = step.approval_required
                              } else if (step.approval) {
                                approvalRequired = step.approval.required || false
                                approvalType = step.approval.type || step.approval.level || ''
                              }
                              
                              return (
                                <TableRow key={stepId}>
                                  <TableCell sx={{ fontFamily: 'monospace' }}>
                                    {stepId}
                                  </TableCell>
                                  <TableCell>{stepName}</TableCell>
                                  <TableCell>
                                    <Chip 
                                      label={stepType} 
                                      size="small" 
                                      color={stepType === 'agent' ? 'primary' : stepType === 'human' ? 'secondary' : stepType === 'decision' ? 'warning' : 'default'}
                                    />
                                  </TableCell>
                                  <TableCell sx={{ fontFamily: 'monospace' }}>
                                    {toolRef}
                                  </TableCell>
                                  <TableCell>
                                    {approvalRequired ? (
                                      <Tooltip title={approvalType ? `Type: ${approvalType}` : 'Approval required'}>
                                        <Chip 
                                          label={approvalType ? `${approvalType}` : 'Required'} 
                                          size="small" 
                                          color="warning" 
                                        />
                                      </Tooltip>
                                    ) : (
                                      <Chip label="Not Required" size="small" color="default" />
                                    )}
                                  </TableCell>
                                  <TableCell>
                                    {step.conditions && Object.keys(step.conditions).length > 0 ? (
                                      <Tooltip title={JSON.stringify(step.conditions, null, 2)}>
                                        <Typography variant="caption" sx={{ fontFamily: 'monospace', cursor: 'help' }}>
                                          {Object.keys(step.conditions).length} condition(s)
                                        </Typography>
                                      </Tooltip>
                                    ) : (
                                      '-'
                                    )}
                                  </TableCell>
                                </TableRow>
                              )
                            })}
                          </TableBody>
                        </Table>
                      </TableContainer>
                    </CardContent>
                  </Card>
                )}

                {/* Playbook Diagram Button */}
                <Card>
                  <CardContent>
                    <Stack direction="row" spacing={2} alignItems="center">
                      <AccountTreeIcon />
                      <Box>
                        <Typography variant="subtitle1">Workflow Diagram</Typography>
                        <Typography variant="body2" color="text.secondary">
                          Visualize this playbook's execution flow
                        </Typography>
                      </Box>
                      <Button
                        variant="outlined"
                        startIcon={<AccountTreeIcon />}
                        onClick={() => setDiagramModalOpen(true)}
                        sx={{ ml: 'auto' }}
                      >
                        View Diagram
                      </Button>
                    </Stack>
                  </CardContent>
                </Card>
              </Stack>
            )}
          </Stack>
        )}
      </TabPanel>

      {/* Tools Tab */}
      <TabPanel value={selectedTab} index={3}>
        {parsedContent.tools.length === 0 ? (
          <Alert severity="info">No tools defined in this pack.</Alert>
        ) : (
          <>
            <Typography variant="h6" gutterBottom>
              Tool Definitions ({parsedContent.tools.length})
            </Typography>
            <Stack spacing={2}>
              {parsedContent.tools.map((tool, index) => {
                const redactedTool = redactToolSecrets(tool)
                return (
                  <Accordion key={tool.id || index}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                        <Typography variant="subtitle1">
                          {tool.name || tool.id || `Tool ${index + 1}`}
                        </Typography>
                        {tool.type && (
                          <Chip label={tool.type} size="small" variant="outlined" />
                        )}
                      </Box>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Stack spacing={2}>
                        <Box>
                          <Typography variant="subtitle2" color="text.secondary">ID</Typography>
                          <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                            {tool.id}
                          </Typography>
                        </Box>
                        {tool.description && (
                          <Box>
                            <Typography variant="subtitle2" color="text.secondary">Description</Typography>
                            <Typography variant="body2">{tool.description}</Typography>
                          </Box>
                        )}
                        {tool.parameters && Object.keys(tool.parameters).length > 0 && (
                          <Box>
                            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                              Parameters (Secrets Redacted)
                            </Typography>
                            <CodeViewer
                              code={JSON.stringify(redactedTool.parameters, null, 2)}
                              language="json"
                              maxHeight={300}
                            />
                          </Box>
                        )}
                      </Stack>
                    </AccordionDetails>
                  </Accordion>
                )
              })}
            </Stack>
          </>
        )}
      </TabPanel>

      {/* Policies Tab */}
      <TabPanel value={selectedTab} index={4}>
        {parsedContent.policies.length === 0 ? (
          <Alert severity="info">No policy clauses defined in this pack.</Alert>
        ) : (
          <>
            <Typography variant="h6" gutterBottom>
              Policy Clauses ({parsedContent.policies.length})
            </Typography>
            <Stack spacing={2}>
              {parsedContent.policies.map((policy, index) => (
                <Accordion key={policy.id || index}>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                      <Typography variant="subtitle1">
                        {policy.name || policy.id || `Policy ${index + 1}`}
                      </Typography>
                      {policy.enforcement && (
                        <Chip 
                          label={policy.enforcement} 
                          size="small" 
                          color={policy.enforcement === 'STRICT' ? 'error' : 'warning'}
                        />
                      )}
                    </Box>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Stack spacing={2}>
                      <Box>
                        <Typography variant="subtitle2" color="text.secondary">ID</Typography>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                          {policy.id}
                        </Typography>
                      </Box>
                      {policy.description && (
                        <Box>
                          <Typography variant="subtitle2" color="text.secondary">Description</Typography>
                          <Typography variant="body2">{policy.description}</Typography>
                        </Box>
                      )}
                      {policy.rules && Object.keys(policy.rules).length > 0 && (
                        <Box>
                          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                            Rules
                          </Typography>
                          <CodeViewer
                            code={JSON.stringify(policy.rules, null, 2)}
                            language="json"
                            maxHeight={300}
                          />
                        </Box>
                      )}
                    </Stack>
                  </AccordionDetails>
                </Accordion>
              ))}
            </Stack>
          </>
        )}
      </TabPanel>

      {/* Playbook Diagram Modal */}
      <Dialog
        open={diagramModalOpen}
        onClose={() => setDiagramModalOpen(false)}
        maxWidth="lg"
        fullWidth
        PaperProps={{
          sx: { height: '80vh' }
        }}
      >
        <DialogTitle>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">
              Playbook Workflow: {selectedPlaybook?.name || selectedPlaybook?.id}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Definition View (Read-Only)
            </Typography>
          </Stack>
        </DialogTitle>
        <DialogContent dividers>
          {selectedPlaybook && selectedPlaybook.steps && selectedPlaybook.steps.length > 0 ? (
            <Box sx={{ height: '100%', width: '100%' }}>
              {(() => {
                const { nodes, edges } = convertPlaybookToWorkflow(selectedPlaybook)
                
                return (
                  <WorkflowViewer
                    exceptionId="playbook-definition"
                    nodes={nodes}
                    edges={edges}
                    currentStage={null}
                    loading={false}
                    error={null}
                  />
                )
              })()}
            </Box>
          ) : (
            <Alert severity="info">
              No steps defined in this playbook to visualize.
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDiagramModalOpen(false)}>
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}