/**
 * Design System Tokens
 * 
 * Unified design tokens for consistent styling across the application.
 * These tokens define colors, spacing, shadows, and radii for both
 * light and dark themes.
 */

// =============================================================================
// COLOR TOKENS
// =============================================================================

/**
 * Light theme colors - Enterprise modern aesthetic
 */
export const lightColors = {
  // Backgrounds
  bg: {
    page: '#f8fafc',           // Main page background (light gray)
    surface: '#ffffff',         // Card/surface background
    surfaceSecondary: '#f1f5f9', // Secondary surfaces
    muted: '#f8fafc',           // Muted backgrounds
    hover: '#f1f5f9',           // Hover state
    selected: '#eff6ff',        // Selected state (blue tint)
  },
  
  // Borders (neutral grays)
  border: {
    default: '#e5e7eb',         // Default border (neutral)
    light: '#f3f4f6',           // Light border
    strong: '#d1d5db',          // Stronger border
    focus: '#3b82f6',           // Focus ring (brand blue)
  },
  
  // Text
  text: {
    primary: '#0f172a',         // Primary text (almost black)
    secondary: '#475569',       // Secondary text
    muted: '#64748b',           // Muted text
    placeholder: '#94a3b8',     // Placeholder text
    inverse: '#ffffff',         // Text on dark backgrounds
  },
  
  // Accent colors
  accent: {
    primary: '#2563eb',         // Primary blue
    primaryHover: '#1d4ed8',    // Primary hover
    primaryLight: '#eff6ff',    // Primary light bg
    secondary: '#0891b2',       // Secondary cyan
  },
}

/**
 * Dark theme colors - For sidebar/header
 */
export const darkColors = {
  bg: {
    primary: '#0B0E14',         // Main background
    secondary: '#151A23',       // Sidebar/cards
    tertiary: '#1a1f2e',        // Elevated surfaces
    elevated: '#1e293b',        // Hover states
  },
  
  border: {
    default: 'rgba(148, 163, 184, 0.1)',
    strong: 'rgba(148, 163, 184, 0.2)',
  },
  
  text: {
    primary: 'rgba(203, 213, 225, 0.95)',
    secondary: 'rgba(148, 163, 184, 0.8)',
    tertiary: 'rgba(148, 163, 184, 0.6)',
  },
}

// =============================================================================
// SEVERITY & STATUS COLORS
// =============================================================================

export const severityColors = {
  // CRITICAL: Muted red - urgent but not alarming
  critical: {
    bg: '#fef2f2',
    border: '#fca5a5',
    text: '#b91c1c',              // Darker, muted red
    icon: '#b91c1c',
  },
  // HIGH: Amber - attention-worthy
  high: {
    bg: '#fffbeb',
    border: '#fcd34d',
    text: '#b45309',              // Darker amber
    icon: '#b45309',
  },
  // MEDIUM: Blue - informational priority
  medium: {
    bg: '#eff6ff',
    border: '#93c5fd',
    text: '#1d4ed8',              // Blue (not yellow)
    icon: '#1d4ed8',
  },
  // LOW: Gray/muted green - low priority
  low: {
    bg: '#f9fafb',
    border: '#d1d5db',
    text: '#4b5563',              // Gray
    icon: '#4b5563',
  },
}

export const statusColors = {
  // Open: Primary blue - needs attention
  open: {
    bg: '#eff6ff',
    border: '#93c5fd',
    text: '#1d4ed8',
    icon: '#1d4ed8',
  },
  // Analyzing: Neutral amber - in process
  analyzing: {
    bg: '#fffbeb',
    border: '#fcd34d',
    text: '#b45309',
    icon: '#b45309',
  },
  // In Progress: Neutral amber - in process
  in_progress: {
    bg: '#fffbeb',
    border: '#fcd34d',
    text: '#b45309',
    icon: '#b45309',
  },
  // Resolved: Muted green - completed
  resolved: {
    bg: '#f0fdf4',
    border: '#86efac',
    text: '#15803d',
    icon: '#15803d',
  },
  // Escalated: Muted red - urgent
  escalated: {
    bg: '#fef2f2',
    border: '#fca5a5',
    text: '#b91c1c',
    icon: '#b91c1c',
  },
  // Closed: Neutral gray - inactive
  closed: {
    bg: '#f9fafb',
    border: '#e5e7eb',
    text: '#6b7280',
    icon: '#6b7280',
  },
}

// =============================================================================
// SPACING SCALE
// =============================================================================

export const spacing = {
  xs: 4,    // 0.25rem
  sm: 8,    // 0.5rem
  md: 16,   // 1rem
  lg: 24,   // 1.5rem
  xl: 32,   // 2rem
  '2xl': 48, // 3rem
  '3xl': 64, // 4rem
}

// =============================================================================
// BORDER RADIUS
// =============================================================================

export const radii = {
  none: 0,
  sm: 4,
  md: 8,
  lg: 12,
  xl: 16,
  full: 9999,
}

// =============================================================================
// SHADOWS
// =============================================================================

export const shadows = {
  none: 'none',
  sm: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
  md: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
  lg: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
  xl: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
  card: '0 1px 3px 0 rgb(0 0 0 / 0.05), 0 1px 2px -1px rgb(0 0 0 / 0.05)',
  cardHover: '0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.05)',
}

// =============================================================================
// TYPOGRAPHY
// =============================================================================

export const typography = {
  fontFamily: [
    '-apple-system',
    'BlinkMacSystemFont',
    '"Segoe UI"',
    'Roboto',
    '"Helvetica Neue"',
    'Arial',
    'sans-serif',
  ].join(','),
  
  // Font sizes
  fontSize: {
    xs: '0.75rem',     // 12px
    sm: '0.8125rem',   // 13px
    base: '0.875rem',  // 14px
    md: '0.9375rem',   // 15px
    lg: '1rem',        // 16px
    xl: '1.125rem',    // 18px
    '2xl': '1.375rem', // 22px
    '3xl': '1.625rem', // 26px
    '4xl': '2rem',     // 32px
  },
  
  // Font weights
  fontWeight: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },
  
  // Line heights
  lineHeight: {
    tight: 1.2,
    snug: 1.375,
    normal: 1.5,
    relaxed: 1.625,
  },
}

// =============================================================================
// TYPOGRAPHY SCALE (Enterprise-Grade Hierarchy)
// =============================================================================

/**
 * Semantic typography scale for consistent UI hierarchy.
 * Use these variants instead of raw fontSize values.
 */
export const typographyScale = {
  /** Page titles - strong, dominant (28-32px) */
  pageTitle: {
    fontSize: '1.875rem',    // 30px
    fontWeight: 700,
    lineHeight: 1.2,
    letterSpacing: '-0.025em',
    color: lightColors.text.primary,
  },
  
  /** Page subtitle - supportive text below title */
  pageSubtitle: {
    fontSize: '0.9375rem',   // 15px
    fontWeight: 400,
    lineHeight: 1.5,
    color: lightColors.text.secondary,
  },
  
  /** Section titles - clear headers (18-20px) */
  sectionTitle: {
    fontSize: '1.125rem',    // 18px
    fontWeight: 600,
    lineHeight: 1.3,
    letterSpacing: '-0.01em',
    color: lightColors.text.primary,
  },
  
  /** Card titles - compact headers (14-15px) */
  cardTitle: {
    fontSize: '0.9375rem',   // 15px
    fontWeight: 600,
    lineHeight: 1.4,
    color: lightColors.text.primary,
  },
  
  /** Card subtitle */
  cardSubtitle: {
    fontSize: '0.8125rem',   // 13px
    fontWeight: 400,
    lineHeight: 1.5,
    color: lightColors.text.secondary,
  },
  
  /** Body text - standard readable (13-14px) */
  body: {
    fontSize: '0.875rem',    // 14px
    fontWeight: 400,
    lineHeight: 1.5,
    color: lightColors.text.primary,
  },
  
  /** Body small */
  bodySmall: {
    fontSize: '0.8125rem',   // 13px
    fontWeight: 400,
    lineHeight: 1.5,
    color: lightColors.text.primary,
  },
  
  /** Muted/secondary body text */
  muted: {
    fontSize: '0.875rem',    // 14px
    fontWeight: 400,
    lineHeight: 1.5,
    color: lightColors.text.muted,
  },
  
  /** KPI values - visually dominant (28-36px) */
  kpiValue: {
    fontSize: '2.25rem',     // 36px
    fontWeight: 700,
    lineHeight: 1.1,
    letterSpacing: '-0.02em',
    color: lightColors.text.primary,
  },
  
  /** KPI labels - uppercase micro (12px) */
  kpiLabel: {
    fontSize: '0.75rem',     // 12px
    fontWeight: 600,
    lineHeight: 1.4,
    letterSpacing: '0.04em',
    textTransform: 'uppercase' as const,
    color: lightColors.text.secondary,
  },
  
  /** Table header - slightly bolder than body */
  tableHeader: {
    fontSize: '0.8125rem',   // 13px
    fontWeight: 600,
    lineHeight: 1.4,
    letterSpacing: '0.01em',
    color: lightColors.text.primary,
  },
  
  /** Table cell - readable but secondary */
  tableCell: {
    fontSize: '0.8125rem',   // 13px
    fontWeight: 400,
    lineHeight: 1.5,
    color: lightColors.text.primary,
  },
  
  /** Label/caption */
  caption: {
    fontSize: '0.75rem',     // 12px
    fontWeight: 500,
    lineHeight: 1.4,
    color: lightColors.text.muted,
  },
}

// =============================================================================
// LAYOUT
// =============================================================================

export const layout = {
  sidebarWidth: 256,
  headerHeight: 64,
  maxContentWidth: 1280,  // Optimal reading width
  containerPadding: {
    xs: 16,
    sm: 24,
    md: 24,
    lg: 24,
  },
  // Consistent spacing rhythm (8px base)
  pageSpacing: {
    headerToContent: 24,   // PageHeader → first section
    betweenSections: 32,   // Between major sections
    insideCard: 20,        // Inside card padding
    cardGap: 24,           // Gap between cards in a grid
    statCardGap: 16,       // Gap between stat cards
  },
}

// =============================================================================
// BREAKPOINTS
// =============================================================================

export const breakpoints = {
  xs: 0,
  sm: 600,
  md: 900,
  lg: 1200,
  xl: 1536,
}

// =============================================================================
// EXPORT ALL TOKENS
// =============================================================================

export const tokens = {
  colors: {
    light: lightColors,
    dark: darkColors,
    severity: severityColors,
    status: statusColors,
  },
  spacing,
  radii,
  shadows,
  typography,
  typographyScale,
  layout,
  breakpoints,
}

export default tokens
