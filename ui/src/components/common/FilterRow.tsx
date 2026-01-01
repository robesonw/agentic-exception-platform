/**
 * FilterRow Component
 * 
 * Reusable horizontal filter layout wrapper.
 * Ensures consistent spacing, alignment, and responsive wrapping.
 * Uses MUI theme tokens for automatic light/dark mode support.
 * 
 * Features:
 * - Horizontal layout with consistent gaps
 * - Wraps nicely on smaller screens
 * - Maintains consistent input heights
 * - Optional end slot for buttons (clear, apply)
 * 
 * Usage:
 *   <FilterRow>
 *     <TextField ... />
 *     <Select ... />
 *   </FilterRow>
 *   
 *   <FilterRow endSlot={<Button>Clear</Button>}>
 *     <TextField ... />
 *   </FilterRow>
 */

import { Box, type SxProps, type Theme } from '@mui/material'

// =============================================================================
// FILTER INPUT STYLE CONSTANTS
// =============================================================================

/**
 * Consistent height for all filter inputs (36px)
 * Apply to TextField, Select, Autocomplete sx props
 */
export const FILTER_INPUT_HEIGHT = 36

/**
 * Standard filter input styles
 * Spread into sx prop: <TextField sx={{ ...filterInputSx, minWidth: 140 }} />
 * Uses theme tokens for automatic light/dark mode support.
 */
export const filterInputSx = {
  '& .MuiInputBase-root': {
    height: FILTER_INPUT_HEIGHT,
    fontSize: '0.8125rem',
    backgroundColor: 'background.paper',
  },
  '& .MuiInputLabel-root': {
    fontSize: '0.8125rem',
  },
  '& .MuiOutlinedInput-notchedOutline': {
    borderColor: 'divider',
  },
}

// =============================================================================
// FILTER ROW COMPONENT
// =============================================================================

export interface FilterRowProps {
  /** Filter controls */
  children: React.ReactNode
  /** Optional end slot (clear button, etc.) */
  endSlot?: React.ReactNode
  /** Gap between items in spacing units (default: 1.5 = 12px) */
  gap?: number
  /** Additional styles */
  sx?: SxProps<Theme>
}

export default function FilterRow({
  children,
  endSlot,
  gap = 1.5,
  sx,
}: FilterRowProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap,
        ...sx,
      }}
    >
      {/* Filter controls */}
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap,
          flexGrow: 1,
        }}
      >
        {children}
      </Box>
      
      {/* End slot (buttons, etc.) */}
      {endSlot && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            flexShrink: 0,
          }}
        >
          {endSlot}
        </Box>
      )}
    </Box>
  )
}

// Re-export for convenience
export { filterInputSx as inputSx }
