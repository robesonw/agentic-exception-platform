import { useState } from 'react'
import {
  Box,
  Paper,
  IconButton,
  Tooltip,
  Typography,
  Collapse,
} from '@mui/material'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'

export interface CodeViewerProps {
  code: string | object
  language?: string
  title?: string
  maxHeight?: number
  collapsible?: boolean
  defaultCollapsed?: boolean
}

/**
 * CodeViewer component for displaying JSON payloads and code
 * Supports syntax highlighting, copy to clipboard, and expand/collapse
 */
export default function CodeViewer({
  code,
  language = 'json',
  title,
  maxHeight = 400,
  collapsible = false,
  defaultCollapsed = false,
}: CodeViewerProps) {
  const [copied, setCopied] = useState(false)
  const [collapsed, setCollapsed] = useState(defaultCollapsed)

  // Convert object to JSON string if needed
  const codeString = typeof code === 'string' ? code : JSON.stringify(code, null, 2)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(codeString)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  return (
    <Paper
      sx={{
        position: 'relative',
        overflow: 'hidden',
        border: '1px solid',
        borderColor: 'divider',
      }}
    >
      {/* Header */}
      {(title || collapsible) && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: 2,
            py: 1,
            borderBottom: '1px solid',
            borderColor: 'divider',
            bgcolor: 'background.default',
          }}
        >
          {title && (
            <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
              {title}
            </Typography>
          )}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Tooltip title={copied ? 'Copied!' : 'Copy to clipboard'}>
              <IconButton size="small" onClick={handleCopy}>
                <ContentCopyIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            {collapsible && (
              <IconButton
                size="small"
                onClick={() => setCollapsed(!collapsed)}
              >
                {collapsed ? <ExpandMoreIcon /> : <ExpandLessIcon />}
              </IconButton>
            )}
          </Box>
        </Box>
      )}

      {/* Code content */}
      <Collapse in={!collapsed}>
        <Box
          sx={{
            maxHeight: collapsed ? 0 : maxHeight,
            overflow: 'auto',
            '& pre': {
              margin: 0,
              padding: 2,
              fontSize: '0.875rem',
              lineHeight: 1.5,
            },
          }}
        >
          <SyntaxHighlighter
            language={language}
            style={vscDarkPlus}
            customStyle={{
              margin: 0,
              padding: 2,
              background: 'transparent',
            }}
          >
            {codeString}
          </SyntaxHighlighter>
        </Box>
      </Collapse>

      {/* Copy button if no header */}
      {!title && !collapsible && (
        <Box
          sx={{
            position: 'absolute',
            top: 8,
            right: 8,
          }}
        >
          <Tooltip title={copied ? 'Copied!' : 'Copy to clipboard'}>
            <IconButton size="small" onClick={handleCopy}>
              <ContentCopyIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      )}
    </Paper>
  )
}

