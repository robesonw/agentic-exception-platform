import { useState } from 'react'
import {
  Box,
  Card,
  CardContent,
  Typography,
  Alert,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import CardSkeleton from '../common/CardSkeleton.tsx'
import { useExplanation } from '../../hooks/useExplanations.ts'
import { formatDateTime } from '../../utils/dateFormat.ts'
import type { ExplanationFormat } from '../../types'

/**
 * Props for ExceptionExplanationTab component
 */
export interface ExceptionExplanationTabProps {
  /** Exception identifier */
  exceptionId: string
}

/**
 * Render text format explanation
 */
function renderTextExplanation(explanation: string) {
  // Split by newlines and render as paragraphs
  const paragraphs = explanation.split('\n').filter((p) => p.trim().length > 0)

  return (
    <Box>
      {paragraphs.map((paragraph, index) => (
        <Typography key={index} variant="body1" paragraph>
          {paragraph}
        </Typography>
      ))}
    </Box>
  )
}

/**
 * Render JSON format explanation
 */
function renderJsonExplanation(explanation: Record<string, unknown>) {
  const jsonString = JSON.stringify(explanation, null, 2)

  return (
    <Box>
      <SyntaxHighlighter
        language="json"
        style={vscDarkPlus}
        customStyle={{
          borderRadius: 4,
          fontSize: '0.875rem',
          margin: 0,
        }}
      >
        {jsonString}
      </SyntaxHighlighter>
    </Box>
  )
}

/**
 * Render structured format explanation
 */
function renderStructuredExplanation(explanation: Record<string, unknown>) {
  // Common structured fields that might be present
  const commonFields = [
    'reasons',
    'factors',
    'recommended_actions',
    'decision',
    'confidence',
    'summary',
    'key_points',
    'context',
  ]

  // Extract known fields and remaining fields
  const knownFields: Array<{ key: string; value: unknown }> = []
  const remainingFields: Array<{ key: string; value: unknown }> = []

  Object.entries(explanation).forEach(([key, value]) => {
    if (commonFields.includes(key)) {
      knownFields.push({ key, value })
    } else {
      remainingFields.push({ key, value })
    }
  })

  return (
    <Stack spacing={3}>
      {/* Known structured fields */}
      {knownFields.map(({ key, value }) => (
        <Card key={key} variant="outlined">
          <CardContent>
            <Typography variant="subtitle2" gutterBottom sx={{ textTransform: 'capitalize', fontWeight: 'medium' }}>
              {key.replace(/_/g, ' ')}
            </Typography>
            {Array.isArray(value) ? (
              <Stack spacing={1} sx={{ mt: 1 }}>
                {value.map((item, index) => (
                  <Box key={index} sx={{ pl: 2, borderLeft: 2, borderColor: 'divider' }}>
                    <Typography variant="body2">
                      {typeof item === 'object' ? JSON.stringify(item, null, 2) : String(item)}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            ) : typeof value === 'object' && value !== null ? (
              <Box sx={{ mt: 1 }}>
                <SyntaxHighlighter
                  language="json"
                  style={vscDarkPlus}
                  customStyle={{
                    borderRadius: 4,
                    fontSize: '0.875rem',
                    margin: 0,
                  }}
                >
                  {JSON.stringify(value, null, 2)}
                </SyntaxHighlighter>
              </Box>
            ) : (
              <Typography variant="body2" sx={{ mt: 1 }}>
                {String(value)}
              </Typography>
            )}
          </CardContent>
        </Card>
      ))}

      {/* Remaining fields */}
      {remainingFields.length > 0 && (
        <Card variant="outlined">
          <CardContent>
            <Typography variant="subtitle2" gutterBottom>
              Additional Information
            </Typography>
            <Stack spacing={2} sx={{ mt: 1 }}>
              {remainingFields.map(({ key, value }) => (
                <Box key={key}>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    {key.replace(/_/g, ' ')}:
                  </Typography>
                  {typeof value === 'object' && value !== null ? (
                    <SyntaxHighlighter
                      language="json"
                      style={vscDarkPlus}
                      customStyle={{
                        borderRadius: 4,
                        fontSize: '0.875rem',
                        margin: 0,
                      }}
                    >
                      {JSON.stringify(value, null, 2)}
                    </SyntaxHighlighter>
                  ) : (
                    <Typography variant="body2">{String(value)}</Typography>
                  )}
                </Box>
              ))}
            </Stack>
          </CardContent>
        </Card>
      )}
    </Stack>
  )
}

/**
 * Exception Explanation Tab Component
 * 
 * Displays the explanation for an exception in various formats:
 * - Text: Natural language explanation
 * - JSON: Raw JSON data with syntax highlighting
 * - Structured: Key fields displayed in organized cards
 */
export default function ExceptionExplanationTab({ exceptionId }: ExceptionExplanationTabProps) {
  const [format, setFormat] = useState<ExplanationFormat>('text')

  const { data, isLoading, isError, error } = useExplanation(exceptionId, { format })

  // Handle format change
  const handleFormatChange = (_event: React.MouseEvent<HTMLElement>, newFormat: ExplanationFormat | null) => {
    if (newFormat !== null) {
      setFormat(newFormat)
    }
  }

  // Loading state
  if (isLoading) {
    return (
      <Stack spacing={2}>
        <CardSkeleton lines={6} />
      </Stack>
    )
  }

  // Error state
  if (isError) {
    return (
      <Alert severity="error">
        Failed to load explanation: {error?.message || 'Unknown error'}
      </Alert>
    )
  }

  // Empty state
  if (!data) {
    return (
      <Alert severity="info">
        No explanation is available for this exception yet.
      </Alert>
    )
  }

  const { explanation, format: responseFormat, version } = data

  // Render explanation based on format
  let explanationContent: React.ReactNode

  if (responseFormat === 'text' && typeof explanation === 'string') {
    explanationContent = renderTextExplanation(explanation)
  } else if (responseFormat === 'json' && typeof explanation === 'object' && explanation !== null) {
    explanationContent = renderJsonExplanation(explanation as Record<string, unknown>)
  } else if (responseFormat === 'structured' && typeof explanation === 'object' && explanation !== null) {
    explanationContent = renderStructuredExplanation(explanation as Record<string, unknown>)
  } else {
    // Fallback: try to render as JSON
    explanationContent = (
      <Box>
        <Alert severity="warning" sx={{ mb: 2 }}>
          Unexpected explanation format. Displaying as JSON.
        </Alert>
        <SyntaxHighlighter
          language="json"
          style={vscDarkPlus}
          customStyle={{
            borderRadius: 4,
            fontSize: '0.875rem',
            margin: 0,
          }}
        >
          {JSON.stringify(explanation, null, 2)}
        </SyntaxHighlighter>
      </Box>
    )
  }

  return (
    <Box>
      {/* Format selector */}
      <Box sx={{ mb: 3 }}>
        <ToggleButtonGroup
          value={format}
          exclusive
          onChange={handleFormatChange}
          aria-label="explanation format"
          size="small"
        >
          <ToggleButton value="text" aria-label="text format">
            Text
          </ToggleButton>
          <ToggleButton value="json" aria-label="json format">
            JSON
          </ToggleButton>
          <ToggleButton value="structured" aria-label="structured format">
            Structured
          </ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {/* Version info */}
      {version && (
        <Box sx={{ mb: 2 }}>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
            <Typography variant="caption" color="text.secondary">
              Explanation v{version.version}
            </Typography>
            {version.timestamp && (
              <>
                <Typography variant="caption" color="text.secondary">
                  •
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Generated at {formatDateTime(version.timestamp)}
                </Typography>
              </>
            )}
          </Stack>
        </Box>
      )}

      {/* Explanation content */}
      <Card>
        <CardContent>
          {explanationContent}
        </CardContent>
      </Card>
    </Box>
  )
}

