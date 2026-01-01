/**
 * Dev-only debug overlay (never ship to prod)
 * 
 * This component displays current theme values to verify the design system
 * is properly wired. It is ONLY rendered in development mode.
 * 
 * Shows:
 * - Theme palette mode (light/dark)
 * - Typography font family
 * - Computed body background color
 * - Primary palette color
 */
import { useTheme } from '@mui/material/styles'
import { Box, Typography, Paper } from '@mui/material'
import { useEffect, useState } from 'react'

// Dev-only debug overlay (never ship to prod)
// Wrapper component that guards rendering at the boundary
export function StyleProbe() {
  // Guard at component boundary - return null in production
  if (!import.meta.env.DEV) {
    return null
  }
  
  // Only render the actual probe in dev mode
  return <StyleProbeContent />
}

// Internal component with hooks - only rendered in dev
function StyleProbeContent() {
  const theme = useTheme()
  const [computedBg, setComputedBg] = useState<string>('')

  useEffect(() => {
    // Get computed body background color
    const bodyBg = window.getComputedStyle(document.body).backgroundColor
    setComputedBg(bodyBg)
  }, [])

  return (
    <Paper
      elevation={0}
      sx={{
        position: 'fixed',
        bottom: 8,
        right: 8,
        zIndex: 9999,
        p: 1.5,
        fontSize: '11px',
        fontFamily: 'monospace',
        backgroundColor: 'rgba(0, 0, 0, 0.85)',
        color: '#00ff00',
        borderRadius: 1,
        maxWidth: 280,
        border: '1px solid rgba(0, 255, 0, 0.3)',
      }}
    >
      <Typography
        variant="caption"
        sx={{
          fontFamily: 'monospace',
          fontSize: '10px',
          color: '#00ff00',
          fontWeight: 'bold',
          display: 'block',
          mb: 0.5,
          borderBottom: '1px solid rgba(0, 255, 0, 0.3)',
          pb: 0.5,
        }}
      >
        🔍 STYLE PROBE (DEV ONLY)
      </Typography>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.25 }}>
        <ProbeRow label="palette.mode" value={theme.palette.mode} />
        <ProbeRow 
          label="typography.fontFamily" 
          value={theme.typography.fontFamily?.toString().substring(0, 30) + '...'} 
        />
        <ProbeRow label="palette.primary.main" value={theme.palette.primary.main} />
        <ProbeRow label="palette.background.default" value={theme.palette.background.default} />
        <ProbeRow label="computed body bg" value={computedBg} />
        <ProbeRow label="palette.text.primary" value={theme.palette.text.primary} />
      </Box>
    </Paper>
  )
}

function ProbeRow({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ display: 'flex', gap: 1, fontSize: '10px' }}>
      <Typography
        component="span"
        sx={{ 
          color: '#888', 
          fontFamily: 'monospace', 
          fontSize: '10px',
          minWidth: 140,
        }}
      >
        {label}:
      </Typography>
      <Typography
        component="span"
        sx={{ 
          color: '#0f0', 
          fontFamily: 'monospace', 
          fontSize: '10px',
          wordBreak: 'break-all',
        }}
      >
        {value}
      </Typography>
    </Box>
  )
}

export default StyleProbe
