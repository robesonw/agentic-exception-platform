import { Box, Card, CardContent, Typography, Alert, Stack, Chip, Accordion, AccordionSummary, AccordionDetails, Link } from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import CardSkeleton from '../common/CardSkeleton.tsx'
import { useExceptionEvidence } from '../../hooks/useExceptions.ts'
import { Link as RouterLink } from 'react-router-dom'
import { formatDateTime } from '../../utils/dateFormat.ts'
import type { RAGResult, ToolOutput, AgentEvidence } from '../../types'

/**
 * Props for ExceptionEvidenceTab component
 */
export interface ExceptionEvidenceTabProps {
  /** Exception identifier */
  exceptionId: string
}

/**
 * Format similarity score as percentage
 */
function formatSimilarityScore(score?: number): string {
  if (score === undefined || score === null) {
    return 'N/A'
  }
  return `${Math.round(score * 100)}%`
}


/**
 * RAG Results Section Component
 */
interface RAGResultsSectionProps {
  ragResults: RAGResult[]
}

function RAGResultsSection({ ragResults }: RAGResultsSectionProps) {
  if (ragResults.length === 0) {
    return (
      <Alert severity="info" sx={{ mb: 3 }}>
        No RAG results available.
      </Alert>
    )
  }

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Similar Exceptions (RAG Results)
        </Typography>
        <Stack spacing={2}>
          {ragResults.map((result, index) => {
            const score = result.score
            const summary = typeof result === 'object' && 'summary' in result ? String(result.summary) : undefined

            return (
              <Card key={index} variant="outlined">
                <CardContent>
                  <Stack spacing={1}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 1 }}>
                      {result.exception_id ? (
                        <Link
                          component={RouterLink}
                          to={`/exceptions/${result.exception_id}`}
                          sx={{ textDecoration: 'none', color: 'primary.main' }}
                        >
                          <Typography variant="subtitle2" sx={{ fontFamily: 'monospace', '&:hover': { textDecoration: 'underline' } }}>
                            {result.exception_id}
                          </Typography>
                        </Link>
                      ) : (
                        <Typography variant="subtitle2" color="text.secondary">
                          Similar Exception #{index + 1}
                        </Typography>
                      )}
                      {score !== undefined && (
                        <Chip
                          label={`Similarity: ${formatSimilarityScore(score)}`}
                          size="small"
                          color={score > 0.8 ? 'success' : score > 0.5 ? 'warning' : 'default'}
                        />
                      )}
                    </Box>
                    {summary && (
                      <Typography variant="body2" color="text.secondary">
                        {summary}
                      </Typography>
                    )}
                    {/* Additional RAG result fields */}
                    {Object.entries(result).map(([key, value]) => {
                      if (key === 'exception_id' || key === 'score' || key === 'summary') {
                        return null
                      }
                      const displayValue = typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)
                      return (
                        <Box key={key}>
                          <Typography variant="caption" color="text.secondary">
                            {key}:
                          </Typography>
                          <Typography variant="body2">
                            {displayValue}
                          </Typography>
                        </Box>
                      )
                    })}
                  </Stack>
                </CardContent>
              </Card>
            )
          })}
        </Stack>
      </CardContent>
    </Card>
  )
}

/**
 * Tool Outputs Section Component
 */
interface ToolOutputsSectionProps {
  toolOutputs: ToolOutput[]
}

function ToolOutputsSection({ toolOutputs }: ToolOutputsSectionProps) {
  if (toolOutputs.length === 0) {
    return (
      <Alert severity="info" sx={{ mb: 3 }}>
        No tool outputs recorded.
      </Alert>
    )
  }

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Tool Outputs
        </Typography>
        <Stack spacing={2}>
          {toolOutputs.map((output, index) => {
            const toolName = output.tool_name || `Tool ${index + 1}`
            const result = output.result
            const resultString = typeof result === 'object' ? JSON.stringify(result, null, 2) : String(result || 'No output')

            return (
              <Accordion key={index}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                    <Chip label={toolName} size="small" color="primary" />
                    {output.timestamp !== undefined && output.timestamp !== null && (typeof output.timestamp === 'string' || output.timestamp instanceof Date) && (
                      <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
                        {formatDateTime(output.timestamp)}
                      </Typography>
                    )}
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  <Box>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                      Output:
                    </Typography>
                    <Typography
                      variant="body2"
                      component="pre"
                      sx={{
                        fontFamily: 'monospace',
                        fontSize: '0.875rem',
                        bgcolor: 'action.hover',
                        p: 1,
                        borderRadius: 1,
                        overflow: 'auto',
                        maxHeight: 300,
                      }}
                    >
                      {resultString}
                    </Typography>
                    {/* Additional tool output fields */}
                    {Object.entries(output).map(([key, value]) => {
                      if (key === 'tool_name' || key === 'result' || key === 'timestamp') {
                        return null
                      }
                      const displayValue = typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)
                      return (
                        <Box key={key} sx={{ mt: 2 }}>
                          <Typography variant="caption" color="text.secondary">
                            {key}:
                          </Typography>
                          <Typography variant="body2">
                            {displayValue}
                          </Typography>
                        </Box>
                      )
                    })}
                  </Box>
                </AccordionDetails>
              </Accordion>
            )
          })}
        </Stack>
      </CardContent>
    </Card>
  )
}

/**
 * Agent Evidence Section Component
 */
interface AgentEvidenceSectionProps {
  agentEvidence: AgentEvidence[]
}

function AgentEvidenceSection({ agentEvidence }: AgentEvidenceSectionProps) {
  if (agentEvidence.length === 0) {
    return (
      <Alert severity="info" sx={{ mb: 3 }}>
        No agent evidence available.
      </Alert>
    )
  }

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Agent Evidence
        </Typography>
        <Stack spacing={2}>
          {agentEvidence.map((evidence, index) => {
            const agentName = evidence.agent_name || `Agent ${index + 1}`
            const evidenceData = evidence.evidence

            return (
              <Card key={index} variant="outlined">
                <CardContent>
                  <Stack spacing={1.5}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
                      <Chip label={agentName} size="small" color="secondary" />
                      {evidence.timestamp !== undefined && evidence.timestamp !== null && (typeof evidence.timestamp === 'string' || evidence.timestamp instanceof Date) && (
                        <Typography variant="caption" color="text.secondary">
                          {formatDateTime(evidence.timestamp)}
                        </Typography>
                      )}
                    </Box>
                    {evidenceData !== undefined && evidenceData !== null && (
                      <Box>
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                          Evidence:
                        </Typography>
                        <Typography
                          variant="body2"
                          component="pre"
                          sx={{
                            fontFamily: 'monospace',
                            fontSize: '0.875rem',
                            bgcolor: 'action.hover',
                            p: 1,
                            borderRadius: 1,
                            overflow: 'auto',
                            maxHeight: 200,
                          }}
                        >
                          {typeof evidenceData === 'object' ? JSON.stringify(evidenceData, null, 2) : String(evidenceData)}
                        </Typography>
                      </Box>
                    )}
                    {/* Additional evidence fields */}
                    {Object.entries(evidence).map(([key, value]) => {
                      if (key === 'agent_name' || key === 'evidence' || key === 'timestamp') {
                        return null
                      }
                      const displayValue = typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)
                      return (
                        <Box key={key}>
                          <Typography variant="caption" color="text.secondary">
                            {key}:
                          </Typography>
                          <Typography variant="body2">
                            {displayValue}
                          </Typography>
                        </Box>
                      )
                    })}
                  </Stack>
                </CardContent>
              </Card>
            )
          })}
        </Stack>
      </CardContent>
    </Card>
  )
}

/**
 * Exception Evidence Tab Component
 * 
 * Displays evidence chains for an exception, including:
 * - RAG results (similar historical exceptions)
 * - Tool outputs (executed tool results)
 * - Agent evidence (evidence from each agent stage)
 */
export default function ExceptionEvidenceTab({ exceptionId }: ExceptionEvidenceTabProps) {
  const { data, isLoading, isError, error } = useExceptionEvidence(exceptionId)

  // Loading state
  if (isLoading) {
    return (
      <Stack spacing={3}>
        <CardSkeleton lines={6} />
        <CardSkeleton lines={4} />
        <CardSkeleton lines={4} />
      </Stack>
    )
  }

  // Error state
  if (isError) {
    return (
      <Alert severity="error">
        Failed to load evidence: {error?.message || 'Unknown error'}
        <br />
        <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>
          If this exception was just created, evidence may not be available yet. Try refreshing the page.
        </Typography>
      </Alert>
    )
  }

  // Empty state
  if (!data) {
    return (
      <Alert severity="info">
        No evidence is available for this exception yet.
      </Alert>
    )
  }

  const { rag_results = [], tool_outputs = [], agent_evidence = [] } = data

  // Check if all sections are empty
  const hasAnyEvidence = rag_results.length > 0 || tool_outputs.length > 0 || agent_evidence.length > 0

  if (!hasAnyEvidence) {
    return (
      <Alert severity="info">
        No evidence is available for this exception yet.
      </Alert>
    )
  }

  return (
    <Box>
      <RAGResultsSection ragResults={rag_results} />
      <ToolOutputsSection toolOutputs={tool_outputs} />
      <AgentEvidenceSection agentEvidence={agent_evidence} />
    </Box>
  )
}

