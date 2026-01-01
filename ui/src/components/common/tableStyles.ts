/**
 * Table Style Constants
 * 
 * Reusable style constants for consistent table appearance across the app.
 * These can be spread into MUI Table components or used with TableFrame wrapper.
 * 
 * Specs (Base44-style enterprise):
 * - Header height: 44px
 * - Row height: 44px (good click target)
 * - Cell padding: 16px horizontal, 0 vertical (height set by row)
 * - Header: subtle background, uppercase labels, 12px font
 * - Rows: 13px font, subtle hover, light border bottom
 * 
 * NOTE: All colors use MUI theme tokens (e.g., 'background.paper', 'text.primary')
 * so they automatically adapt to light/dark mode.
 */

// =============================================================================
// TABLE DIMENSION CONSTANTS
// =============================================================================

export const TABLE_HEADER_HEIGHT = 44
export const TABLE_ROW_HEIGHT = 44
export const TABLE_CELL_PADDING_X = 2 // MUI spacing (16px)
export const TABLE_CELL_PADDING_Y = 0

// =============================================================================
// TABLE HEADER CELL STYLES
// =============================================================================

/**
 * Styles for table header cells (TableCell in TableHead)
 * Spread into sx prop: <TableCell sx={tableHeaderCellSx}>
 * Uses MUI theme tokens for automatic light/dark mode support.
 */
export const tableHeaderCellSx = {
  backgroundColor: 'background.paper',
  borderBottom: 1,
  borderColor: 'divider',
  fontSize: '0.75rem',       // 12px
  fontWeight: 600,
  textTransform: 'uppercase' as const,
  letterSpacing: '0.03em',
  color: 'text.secondary',
  height: TABLE_HEADER_HEIGHT,
  py: TABLE_CELL_PADDING_Y,
  px: TABLE_CELL_PADDING_X,
  whiteSpace: 'nowrap' as const,
}

// =============================================================================
// TABLE BODY CELL STYLES
// =============================================================================

/**
 * Styles for table body cells (TableCell in TableBody)
 * Spread into sx prop: <TableCell sx={tableBodyCellSx}>
 * Uses MUI theme tokens for automatic light/dark mode support.
 */
export const tableBodyCellSx = {
  fontSize: '0.8125rem',     // 13px
  fontWeight: 400,
  color: 'text.primary',
  py: TABLE_CELL_PADDING_Y,
  px: TABLE_CELL_PADDING_X,
  height: TABLE_ROW_HEIGHT,
  borderBottom: 1,
  borderColor: 'divider',
}

// =============================================================================
// TABLE ROW STYLES
// =============================================================================

/**
 * Styles for table body rows (TableRow in TableBody)
 * Spread into sx prop: <TableRow sx={tableRowSx}>
 * Uses MUI theme tokens for automatic light/dark mode support.
 */
export const tableRowSx = {
  height: TABLE_ROW_HEIGHT,
  '&:hover': {
    backgroundColor: 'action.hover',
  },
  transition: 'background-color 0.1s ease',
}

// =============================================================================
// TABLE CONTAINER STYLES
// =============================================================================

/**
 * Styles for TableContainer
 * Spread into sx prop: <TableContainer sx={tableContainerSx}>
 */
export const tableContainerSx = {
  overflowX: 'auto' as const,
  // Default max height - can be overridden
  maxHeight: 'calc(100vh - 320px)',
}

// =============================================================================
// TABLE PAGINATION STYLES
// =============================================================================

/**
 * Styles for TablePagination
 * Spread into sx prop: <TablePagination sx={tablePaginationSx}>
 * Uses MUI theme tokens for automatic light/dark mode support.
 */
export const tablePaginationSx = {
  borderTop: 1,
  borderColor: 'divider',
  backgroundColor: 'background.paper',
  minHeight: 48,
  '& .MuiTablePagination-toolbar': {
    minHeight: 48,
  },
  '& .MuiTablePagination-selectLabel, & .MuiTablePagination-displayedRows': {
    fontSize: '0.75rem',
    color: 'text.secondary',
  },
  '& .MuiTablePagination-select': {
    fontSize: '0.8125rem',
  },
}

// =============================================================================
// SORT LABEL STYLES
// =============================================================================

/**
 * Styles for TableSortLabel (active state)
 * Uses MUI theme tokens for automatic light/dark mode support.
 */
export const tableSortLabelSx = {
  '&.Mui-active': {
    color: 'text.primary',
  },
}
