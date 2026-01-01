/**
 * ═══════════════════════════════════════════════════════════════════════════════
 * SENTINAI GLOBAL DESIGN SYSTEM
 * ═══════════════════════════════════════════════════════════════════════════════
 * 
 * Enterprise-grade design system inspired by Base44-quality SaaS platforms.
 * This file defines the complete visual language for the SentinAI platform.
 * 
 * DESIGN PRINCIPLES:
 * 1. Clean & Professional - No visual noise, deliberate whitespace
 * 2. Scannable - Clear hierarchy, users find info instantly
 * 3. Calm & Confident - Muted colors, no alarms unless critical
 * 4. Consistent - Same patterns everywhere, zero surprises
 * 5. Accessible - WCAG 2.1 AA compliant contrast ratios
 * 
 * ═══════════════════════════════════════════════════════════════════════════════
 */

// =============================================================================
// SECTION 1: TYPOGRAPHY SYSTEM
// =============================================================================
/**
 * Typography Hierarchy Explanation:
 * 
 * We use Inter (or system fallback) as the primary typeface for its excellent
 * legibility at small sizes and professional appearance.
 * 
 * HIERARCHY LEVELS (largest to smallest):
 * 
 * 1. PAGE TITLE (28-32px, Bold)
 *    - One per page, identifies the current view
 *    - Example: "Operations Center", "Admin Dashboard"
 *    - Tight letter-spacing for visual weight
 * 
 * 2. SECTION TITLE (18-20px, Semibold)
 *    - Divides page into logical sections
 *    - Example: "Recent Exceptions", "Worker Health"
 *    - Clear but not overwhelming
 * 
 * 3. CARD TITLE (14-15px, Semibold)
 *    - Labels individual cards/widgets
 *    - Example: "Critical Issues", "SLA Compliance"
 *    - Compact but distinct from body text
 * 
 * 4. TABLE HEADER (13px, Semibold)
 *    - Column labels in data tables
 *    - Slightly heavier than cell text
 *    - Uppercase optional for emphasis
 * 
 * 5. BODY TEXT (13-14px, Regular)
 *    - Main readable content
 *    - Descriptions, explanations, cell content
 *    - Optimal line-height for scanning
 * 
 * 6. MUTED/METADATA (12-13px, Regular/Medium)
 *    - Timestamps, IDs, secondary info
 *    - Reduced contrast, doesn't compete
 *    - Example: "Updated 2 hours ago"
 * 
 * 7. KPI/NUMERIC (28-48px, Bold)
 *    - Large numbers that draw attention
 *    - Stat cards, dashboards
 *    - Tight letter-spacing, tabular numerals
 */

export const fontFamily = {
  // Primary: Inter for UI, with excellent system fallbacks
  primary: [
    'Inter',
    '-apple-system',
    'BlinkMacSystemFont',
    '"Segoe UI"',
    'Roboto',
    '"Helvetica Neue"',
    'Arial',
    'sans-serif',
  ].join(', '),
  
  // Monospace: For IDs, code, technical content
  mono: [
    '"JetBrains Mono"',
    '"Fira Code"',
    'Consolas',
    '"Liberation Mono"',
    'Menlo',
    'monospace',
  ].join(', '),
};

export const fontSize = {
  // Pixel reference for clarity (rem values used)
  '2xs': '0.6875rem',   // 11px - micro labels
  'xs': '0.75rem',      // 12px - captions, metadata
  'sm': '0.8125rem',    // 13px - table cells, compact UI
  'base': '0.875rem',   // 14px - body text default
  'md': '0.9375rem',    // 15px - slightly emphasized body
  'lg': '1rem',         // 16px - large body
  'xl': '1.125rem',     // 18px - section titles
  '2xl': '1.25rem',     // 20px - large section titles
  '3xl': '1.5rem',      // 24px - small page titles
  '4xl': '1.75rem',     // 28px - page titles
  '5xl': '2rem',        // 32px - large page titles
  '6xl': '2.25rem',     // 36px - KPI values
  '7xl': '3rem',        // 48px - hero KPIs
};

export const fontWeight = {
  normal: 400,
  medium: 500,
  semibold: 600,
  bold: 700,
};

export const lineHeight = {
  none: 1,
  tight: 1.2,
  snug: 1.375,
  normal: 1.5,
  relaxed: 1.625,
  loose: 2,
};

export const letterSpacing = {
  tighter: '-0.03em',
  tight: '-0.02em',
  normal: '0',
  wide: '0.025em',
  wider: '0.05em',
  widest: '0.1em',
};

/**
 * Semantic Typography Presets
 * Use these instead of raw values for consistency
 */
export const typography = {
  // Page-level
  pageTitle: {
    fontFamily: fontFamily.primary,
    fontSize: fontSize['4xl'],      // 28px
    fontWeight: fontWeight.bold,
    lineHeight: lineHeight.tight,
    letterSpacing: letterSpacing.tight,
  },
  pageSubtitle: {
    fontFamily: fontFamily.primary,
    fontSize: fontSize.md,          // 15px
    fontWeight: fontWeight.normal,
    lineHeight: lineHeight.normal,
    letterSpacing: letterSpacing.normal,
  },
  
  // Section-level
  sectionTitle: {
    fontFamily: fontFamily.primary,
    fontSize: fontSize.xl,          // 18px
    fontWeight: fontWeight.semibold,
    lineHeight: lineHeight.snug,
    letterSpacing: letterSpacing.tight,
  },
  sectionSubtitle: {
    fontFamily: fontFamily.primary,
    fontSize: fontSize.sm,          // 13px
    fontWeight: fontWeight.normal,
    lineHeight: lineHeight.normal,
    letterSpacing: letterSpacing.normal,
  },
  
  // Card-level
  cardTitle: {
    fontFamily: fontFamily.primary,
    fontSize: fontSize.md,          // 15px
    fontWeight: fontWeight.semibold,
    lineHeight: lineHeight.snug,
    letterSpacing: letterSpacing.normal,
  },
  cardSubtitle: {
    fontFamily: fontFamily.primary,
    fontSize: fontSize.sm,          // 13px
    fontWeight: fontWeight.normal,
    lineHeight: lineHeight.normal,
    letterSpacing: letterSpacing.normal,
  },
  
  // Table
  tableHeader: {
    fontFamily: fontFamily.primary,
    fontSize: fontSize.sm,          // 13px
    fontWeight: fontWeight.semibold,
    lineHeight: lineHeight.snug,
    letterSpacing: letterSpacing.wide,
  },
  tableCell: {
    fontFamily: fontFamily.primary,
    fontSize: fontSize.sm,          // 13px
    fontWeight: fontWeight.normal,
    lineHeight: lineHeight.normal,
    letterSpacing: letterSpacing.normal,
  },
  
  // Body text
  body: {
    fontFamily: fontFamily.primary,
    fontSize: fontSize.base,        // 14px
    fontWeight: fontWeight.normal,
    lineHeight: lineHeight.normal,
    letterSpacing: letterSpacing.normal,
  },
  bodySmall: {
    fontFamily: fontFamily.primary,
    fontSize: fontSize.sm,          // 13px
    fontWeight: fontWeight.normal,
    lineHeight: lineHeight.normal,
    letterSpacing: letterSpacing.normal,
  },
  bodyLarge: {
    fontFamily: fontFamily.primary,
    fontSize: fontSize.md,          // 15px
    fontWeight: fontWeight.normal,
    lineHeight: lineHeight.relaxed,
    letterSpacing: letterSpacing.normal,
  },
  
  // Metadata/muted
  caption: {
    fontFamily: fontFamily.primary,
    fontSize: fontSize.xs,          // 12px
    fontWeight: fontWeight.medium,
    lineHeight: lineHeight.snug,
    letterSpacing: letterSpacing.normal,
  },
  metadata: {
    fontFamily: fontFamily.primary,
    fontSize: fontSize.xs,          // 12px
    fontWeight: fontWeight.normal,
    lineHeight: lineHeight.normal,
    letterSpacing: letterSpacing.normal,
  },
  
  // KPI/Numeric emphasis
  kpiLarge: {
    fontFamily: fontFamily.primary,
    fontSize: fontSize['7xl'],      // 48px
    fontWeight: fontWeight.bold,
    lineHeight: lineHeight.none,
    letterSpacing: letterSpacing.tight,
    fontVariantNumeric: 'tabular-nums',
  },
  kpiMedium: {
    fontFamily: fontFamily.primary,
    fontSize: fontSize['6xl'],      // 36px
    fontWeight: fontWeight.bold,
    lineHeight: lineHeight.tight,
    letterSpacing: letterSpacing.tight,
    fontVariantNumeric: 'tabular-nums',
  },
  kpiSmall: {
    fontFamily: fontFamily.primary,
    fontSize: fontSize['3xl'],      // 24px
    fontWeight: fontWeight.bold,
    lineHeight: lineHeight.tight,
    letterSpacing: letterSpacing.tight,
    fontVariantNumeric: 'tabular-nums',
  },
  kpiLabel: {
    fontFamily: fontFamily.primary,
    fontSize: fontSize.xs,          // 12px
    fontWeight: fontWeight.semibold,
    lineHeight: lineHeight.snug,
    letterSpacing: letterSpacing.wider,
    textTransform: 'uppercase' as const,
  },
  
  // Monospace (for IDs, code)
  mono: {
    fontFamily: fontFamily.mono,
    fontSize: fontSize.sm,          // 13px
    fontWeight: fontWeight.medium,
    lineHeight: lineHeight.normal,
    letterSpacing: letterSpacing.normal,
  },
  monoSmall: {
    fontFamily: fontFamily.mono,
    fontSize: fontSize.xs,          // 12px
    fontWeight: fontWeight.normal,
    lineHeight: lineHeight.normal,
    letterSpacing: letterSpacing.normal,
  },
};


// =============================================================================
// SECTION 2: SPACING SYSTEM
// =============================================================================
/**
 * Spacing Rhythm Explanation:
 * 
 * We use an 8px base grid for all spacing. This creates visual harmony
 * and makes spacing decisions automatic.
 * 
 * SPACING SCALE:
 * - 4px  (0.5) - Micro: icon-to-text, tight inline spacing
 * - 8px  (1)   - Small: related elements, button padding
 * - 12px (1.5) - Compact: dense UI elements
 * - 16px (2)   - Medium: standard component spacing
 * - 20px (2.5) - Comfortable: card padding, input height
 * - 24px (3)   - Large: section gaps, page padding
 * - 32px (4)   - XL: major section separators
 * - 40px (5)   - 2XL: page sections
 * - 48px (6)   - 3XL: large gaps
 * - 64px (8)   - 4XL: hero sections, major breaks
 * 
 * USAGE PATTERNS:
 * 
 * 1. PAGE LAYOUT
 *    - Page horizontal padding: 24-32px
 *    - Page vertical padding: 24px
 *    - Max content width: 1280-1440px
 * 
 * 2. HEADER TO CONTENT
 *    - PageHeader → First section: 24px
 *    - Keeps title connected to content
 * 
 * 3. BETWEEN SECTIONS
 *    - Section → Section: 32-40px
 *    - Clear separation without excess whitespace
 * 
 * 4. INSIDE CARDS
 *    - Card padding: 20-24px
 *    - Title → Content: 16px
 *    - Between items: 12-16px
 * 
 * 5. TABLE ROWS
 *    - Row height: 44-48px (clickable target)
 *    - Cell padding: 12-16px horizontal, 8-12px vertical
 * 
 * 6. GRID GAPS
 *    - Stat cards: 16px
 *    - Content cards: 24px
 *    - Large cards: 32px
 */

export const spacing = {
  // Base scale (in pixels, use with MUI sx as spacing units or px)
  px: '1px',
  0: '0',
  0.5: '0.125rem',    // 2px
  1: '0.25rem',       // 4px
  1.5: '0.375rem',    // 6px
  2: '0.5rem',        // 8px
  2.5: '0.625rem',    // 10px
  3: '0.75rem',       // 12px
  3.5: '0.875rem',    // 14px
  4: '1rem',          // 16px
  5: '1.25rem',       // 20px
  6: '1.5rem',        // 24px
  7: '1.75rem',       // 28px
  8: '2rem',          // 32px
  9: '2.25rem',       // 36px
  10: '2.5rem',       // 40px
  11: '2.75rem',      // 44px
  12: '3rem',         // 48px
  14: '3.5rem',       // 56px
  16: '4rem',         // 64px
  20: '5rem',         // 80px
  24: '6rem',         // 96px
};

/**
 * Semantic Spacing Presets
 * Use these for consistent page layout
 */
export const layoutSpacing = {
  // Page layout
  pageMaxWidth: '1280px',
  pageMaxWidthWide: '1440px',
  pagePaddingX: spacing[6],       // 24px
  pagePaddingY: spacing[6],       // 24px
  
  // Header spacing
  headerToContent: spacing[6],    // 24px
  titleToSubtitle: spacing[1],    // 4px
  
  // Section spacing
  betweenSections: spacing[8],    // 32px
  betweenSectionsLarge: spacing[10], // 40px
  sectionTitleToContent: spacing[4], // 16px
  
  // Card spacing
  cardPadding: spacing[5],        // 20px
  cardPaddingCompact: spacing[4], // 16px
  cardPaddingLarge: spacing[6],   // 24px
  cardTitleToContent: spacing[4], // 16px
  cardItemGap: spacing[3],        // 12px
  
  // Grid gaps
  gridGapSm: spacing[3],          // 12px - tight grids
  gridGapMd: spacing[4],          // 16px - stat cards
  gridGapLg: spacing[6],          // 24px - content cards
  gridGapXl: spacing[8],          // 32px - large cards
  
  // Table spacing
  tableRowHeight: '44px',
  tableRowHeightCompact: '40px',
  tableRowHeightLarge: '52px',
  tableCellPaddingX: spacing[4],  // 16px
  tableCellPaddingY: spacing[3],  // 12px
  tableHeaderPaddingY: spacing[3], // 12px
  
  // Component spacing
  inputHeight: '40px',
  inputHeightSm: '32px',
  inputHeightLg: '48px',
  buttonPaddingX: spacing[4],     // 16px
  buttonPaddingY: spacing[2],     // 8px
  iconTextGap: spacing[2],        // 8px
  badgePaddingX: spacing[2],      // 8px
  badgePaddingY: spacing[1],      // 4px
};


// =============================================================================
// SECTION 3: COLOR SYSTEM
// =============================================================================
/**
 * Color Usage Rules:
 * 
 * PRINCIPLE: Colors should inform, not alarm. Use semantic colors sparingly
 * and rely on neutral grays for most UI elements.
 * 
 * 1. PRIMARY BRAND COLOR (Blue #2563eb)
 *    - Primary buttons
 *    - Active navigation items
 *    - Links
 *    - Focus rings
 *    - Selected states
 *    NEVER use for: backgrounds, large areas, decorative purposes
 * 
 * 2. NEUTRAL GRAYSCALE
 *    - 90% of the UI should be grayscale
 *    - Creates calm, professional appearance
 *    - Lets semantic colors stand out when needed
 * 
 * 3. SEMANTIC COLORS (use as badges/indicators only)
 *    - Critical/Error: Muted red - actual problems
 *    - Warning/High: Amber - needs attention
 *    - Info/Medium: Blue - informational
 *    - Success/Resolved: Green - completed/healthy
 *    NEVER use for: full backgrounds, decorative purposes
 * 
 * 4. BACKGROUND LAYERS (light to dark)
 *    - Page bg: #f8fafc (very light gray)
 *    - Card bg: #ffffff (pure white)
 *    - Table header bg: #f9fafb (subtle tint)
 *    - Hover state: #f3f4f6
 *    - Selected state: #eff6ff (blue tint)
 * 
 * 5. BORDERS & DIVIDERS
 *    - Use subtle, not heavy
 *    - Default: #e5e7eb
 *    - Light: #f3f4f6
 *    - Never use dark borders in content area
 */

export const colors = {
  // Brand
  brand: {
    primary: '#2563eb',           // Main brand blue
    primaryHover: '#1d4ed8',      // Darker on hover
    primaryActive: '#1e40af',     // Even darker on active
    primaryLight: '#eff6ff',      // Light blue for backgrounds
    primaryLighter: '#f8faff',    // Very light blue tint
  },
  
  // Neutral grayscale (Slate-based for warmth)
  neutral: {
    0: '#ffffff',
    25: '#fcfcfd',
    50: '#f9fafb',
    100: '#f3f4f6',
    200: '#e5e7eb',
    300: '#d1d5db',
    400: '#9ca3af',
    500: '#6b7280',
    600: '#4b5563',
    700: '#374151',
    800: '#1f2937',
    900: '#111827',
    950: '#030712',
  },
  
  // Background layers
  bg: {
    app: '#f8fafc',               // Main app background
    page: '#f8fafc',              // Page background
    card: '#ffffff',              // Card surfaces
    cardElevated: '#ffffff',      // Elevated cards (same, use shadow)
    tableHeader: '#f9fafb',       // Table header row
    tableRow: '#ffffff',          // Table rows
    tableRowHover: '#f9fafb',     // Table row hover
    tableRowSelected: '#eff6ff',  // Table row selected
    input: '#ffffff',             // Form inputs
    inputDisabled: '#f3f4f6',     // Disabled inputs
    muted: '#f3f4f6',             // Muted backgrounds
    overlay: 'rgba(0, 0, 0, 0.5)', // Modal overlay
  },
  
  // Text colors
  text: {
    primary: '#111827',           // Main text (gray-900)
    secondary: '#4b5563',         // Secondary text (gray-600)
    muted: '#6b7280',             // Muted text (gray-500)
    placeholder: '#9ca3af',       // Placeholder (gray-400)
    disabled: '#d1d5db',          // Disabled text (gray-300)
    inverse: '#ffffff',           // Text on dark backgrounds
    link: '#2563eb',              // Link text
    linkHover: '#1d4ed8',         // Link hover
  },
  
  // Border colors
  border: {
    default: '#e5e7eb',           // Default border (gray-200)
    light: '#f3f4f6',             // Light border (gray-100)
    strong: '#d1d5db',            // Strong border (gray-300)
    focus: '#2563eb',             // Focus ring
    focusRing: 'rgba(37, 99, 235, 0.2)', // Focus ring with opacity
  },
  
  // Semantic colors - MUTED versions for enterprise calm
  semantic: {
    // Success (green)
    success: {
      bg: '#f0fdf4',
      bgSubtle: '#f0fdf4',
      border: '#86efac',
      text: '#15803d',
      icon: '#22c55e',
    },
    // Warning (amber)
    warning: {
      bg: '#fffbeb',
      bgSubtle: '#fffbeb',
      border: '#fcd34d',
      text: '#b45309',
      icon: '#f59e0b',
    },
    // Error/Critical (red)
    error: {
      bg: '#fef2f2',
      bgSubtle: '#fef2f2',
      border: '#fca5a5',
      text: '#b91c1c',
      icon: '#ef4444',
    },
    // Info (blue)
    info: {
      bg: '#eff6ff',
      bgSubtle: '#eff6ff',
      border: '#93c5fd',
      text: '#1d4ed8',
      icon: '#3b82f6',
    },
  },
  
  // Severity colors (for badges only)
  severity: {
    critical: {
      bg: '#fef2f2',
      border: '#fca5a5',
      text: '#b91c1c',
    },
    high: {
      bg: '#fffbeb',
      border: '#fcd34d',
      text: '#b45309',
    },
    medium: {
      bg: '#eff6ff',
      border: '#93c5fd',
      text: '#1d4ed8',
    },
    low: {
      bg: '#f9fafb',
      border: '#e5e7eb',
      text: '#4b5563',
    },
  },
  
  // Status colors (for badges only)
  status: {
    open: {
      bg: '#eff6ff',
      border: '#93c5fd',
      text: '#1d4ed8',
    },
    inProgress: {
      bg: '#fffbeb',
      border: '#fcd34d',
      text: '#b45309',
    },
    resolved: {
      bg: '#f0fdf4',
      border: '#86efac',
      text: '#15803d',
    },
    escalated: {
      bg: '#fef2f2',
      border: '#fca5a5',
      text: '#b91c1c',
    },
    closed: {
      bg: '#f9fafb',
      border: '#e5e7eb',
      text: '#6b7280',
    },
  },
  
  // Dark theme (sidebar only)
  dark: {
    bg: {
      primary: '#0f172a',         // Main dark bg
      secondary: '#1e293b',       // Elevated dark bg
      hover: '#334155',           // Hover state
      active: '#475569',          // Active state
    },
    text: {
      primary: '#f1f5f9',         // Primary text
      secondary: '#94a3b8',       // Secondary text
      muted: '#64748b',           // Muted text
    },
    border: {
      default: '#334155',
      light: '#1e293b',
    },
  },
};


// =============================================================================
// SECTION 4: ELEVATION & RADIUS
// =============================================================================
/**
 * Elevation Strategy:
 * 
 * We use a MINIMAL shadow approach. Most cards use borders, not shadows.
 * This creates a cleaner, more modern enterprise look.
 * 
 * WHEN TO USE SHADOW:
 * - Dropdowns/popovers (elevated above content)
 * - Modals (clearly above page)
 * - Tooltips
 * - Floating action buttons
 * 
 * WHEN TO USE BORDER:
 * - Cards on page
 * - Tables
 * - Form inputs
 * - Most UI containers
 * 
 * RADIUS SCALE:
 * - 0px: None (special cases)
 * - 4px: Small (buttons, inputs, badges)
 * - 6px: Medium-small (chips, tags)
 * - 8px: Medium (cards, modals)
 * - 12px: Large (large cards, panels)
 * - 16px: XL (hero cards, special containers)
 * - 9999px: Full (avatars, pills)
 */

export const radius = {
  none: '0',
  xs: '2px',
  sm: '4px',
  md: '6px',
  lg: '8px',
  xl: '12px',
  '2xl': '16px',
  '3xl': '24px',
  full: '9999px',
};

export const shadow = {
  none: 'none',
  
  // Subtle shadows (for most elevated elements)
  xs: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
  sm: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)',
  md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)',
  lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)',
  xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
  '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
  
  // Semantic shadows
  card: '0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px -1px rgba(0, 0, 0, 0.04)',
  cardHover: '0 4px 6px -1px rgba(0, 0, 0, 0.06), 0 2px 4px -2px rgba(0, 0, 0, 0.04)',
  dropdown: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)',
  modal: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
  tooltip: '0 4px 6px -1px rgba(0, 0, 0, 0.15), 0 2px 4px -2px rgba(0, 0, 0, 0.1)',
  
  // Focus rings
  focusRing: '0 0 0 3px rgba(37, 99, 235, 0.15)',
  focusRingError: '0 0 0 3px rgba(239, 68, 68, 0.15)',
};

/**
 * Semantic elevation presets
 */
export const elevation = {
  // Cards: prefer border over shadow
  card: {
    border: `1px solid ${colors.border.default}`,
    borderRadius: radius.lg,
    shadow: shadow.none, // Use border, not shadow
  },
  cardHoverable: {
    border: `1px solid ${colors.border.default}`,
    borderRadius: radius.lg,
    shadow: shadow.none,
    hoverBorder: `1px solid ${colors.border.strong}`,
    hoverShadow: shadow.cardHover,
  },
  
  // Inputs
  input: {
    border: `1px solid ${colors.border.default}`,
    borderRadius: radius.md,
    focusBorder: `1px solid ${colors.border.focus}`,
    focusShadow: shadow.focusRing,
  },
  
  // Dropdowns/Popovers
  dropdown: {
    border: `1px solid ${colors.border.default}`,
    borderRadius: radius.lg,
    shadow: shadow.dropdown,
  },
  
  // Modals
  modal: {
    border: 'none',
    borderRadius: radius.xl,
    shadow: shadow.modal,
  },
  
  // Tooltips
  tooltip: {
    border: 'none',
    borderRadius: radius.md,
    shadow: shadow.tooltip,
  },
};


// =============================================================================
// SECTION 5: CSS VARIABLES EXPORT
// =============================================================================
/**
 * CSS Custom Properties for global stylesheet
 * Can be injected into :root for CSS-based styling
 */

export const cssVariables = `
:root {
  /* Typography */
  --font-family-primary: ${fontFamily.primary};
  --font-family-mono: ${fontFamily.mono};
  
  /* Font sizes */
  --font-size-2xs: ${fontSize['2xs']};
  --font-size-xs: ${fontSize.xs};
  --font-size-sm: ${fontSize.sm};
  --font-size-base: ${fontSize.base};
  --font-size-md: ${fontSize.md};
  --font-size-lg: ${fontSize.lg};
  --font-size-xl: ${fontSize.xl};
  --font-size-2xl: ${fontSize['2xl']};
  --font-size-3xl: ${fontSize['3xl']};
  --font-size-4xl: ${fontSize['4xl']};
  --font-size-5xl: ${fontSize['5xl']};
  --font-size-6xl: ${fontSize['6xl']};
  --font-size-7xl: ${fontSize['7xl']};
  
  /* Font weights */
  --font-weight-normal: ${fontWeight.normal};
  --font-weight-medium: ${fontWeight.medium};
  --font-weight-semibold: ${fontWeight.semibold};
  --font-weight-bold: ${fontWeight.bold};
  
  /* Line heights */
  --line-height-none: ${lineHeight.none};
  --line-height-tight: ${lineHeight.tight};
  --line-height-snug: ${lineHeight.snug};
  --line-height-normal: ${lineHeight.normal};
  --line-height-relaxed: ${lineHeight.relaxed};
  
  /* Brand colors */
  --color-brand-primary: ${colors.brand.primary};
  --color-brand-primary-hover: ${colors.brand.primaryHover};
  --color-brand-primary-light: ${colors.brand.primaryLight};
  
  /* Neutral colors */
  --color-neutral-0: ${colors.neutral[0]};
  --color-neutral-50: ${colors.neutral[50]};
  --color-neutral-100: ${colors.neutral[100]};
  --color-neutral-200: ${colors.neutral[200]};
  --color-neutral-300: ${colors.neutral[300]};
  --color-neutral-400: ${colors.neutral[400]};
  --color-neutral-500: ${colors.neutral[500]};
  --color-neutral-600: ${colors.neutral[600]};
  --color-neutral-700: ${colors.neutral[700]};
  --color-neutral-800: ${colors.neutral[800]};
  --color-neutral-900: ${colors.neutral[900]};
  
  /* Background colors */
  --color-bg-app: ${colors.bg.app};
  --color-bg-card: ${colors.bg.card};
  --color-bg-table-header: ${colors.bg.tableHeader};
  --color-bg-muted: ${colors.bg.muted};
  
  /* Text colors */
  --color-text-primary: ${colors.text.primary};
  --color-text-secondary: ${colors.text.secondary};
  --color-text-muted: ${colors.text.muted};
  --color-text-placeholder: ${colors.text.placeholder};
  --color-text-link: ${colors.text.link};
  
  /* Border colors */
  --color-border-default: ${colors.border.default};
  --color-border-light: ${colors.border.light};
  --color-border-strong: ${colors.border.strong};
  --color-border-focus: ${colors.border.focus};
  
  /* Semantic colors - Success */
  --color-success-bg: ${colors.semantic.success.bg};
  --color-success-border: ${colors.semantic.success.border};
  --color-success-text: ${colors.semantic.success.text};
  
  /* Semantic colors - Warning */
  --color-warning-bg: ${colors.semantic.warning.bg};
  --color-warning-border: ${colors.semantic.warning.border};
  --color-warning-text: ${colors.semantic.warning.text};
  
  /* Semantic colors - Error */
  --color-error-bg: ${colors.semantic.error.bg};
  --color-error-border: ${colors.semantic.error.border};
  --color-error-text: ${colors.semantic.error.text};
  
  /* Semantic colors - Info */
  --color-info-bg: ${colors.semantic.info.bg};
  --color-info-border: ${colors.semantic.info.border};
  --color-info-text: ${colors.semantic.info.text};
  
  /* Spacing */
  --spacing-1: ${spacing[1]};
  --spacing-2: ${spacing[2]};
  --spacing-3: ${spacing[3]};
  --spacing-4: ${spacing[4]};
  --spacing-5: ${spacing[5]};
  --spacing-6: ${spacing[6]};
  --spacing-8: ${spacing[8]};
  --spacing-10: ${spacing[10]};
  --spacing-12: ${spacing[12]};
  --spacing-16: ${spacing[16]};
  
  /* Layout spacing */
  --layout-page-max-width: ${layoutSpacing.pageMaxWidth};
  --layout-page-padding-x: ${layoutSpacing.pagePaddingX};
  --layout-page-padding-y: ${layoutSpacing.pagePaddingY};
  --layout-header-to-content: ${layoutSpacing.headerToContent};
  --layout-between-sections: ${layoutSpacing.betweenSections};
  --layout-card-padding: ${layoutSpacing.cardPadding};
  --layout-grid-gap-md: ${layoutSpacing.gridGapMd};
  --layout-grid-gap-lg: ${layoutSpacing.gridGapLg};
  --layout-table-row-height: ${layoutSpacing.tableRowHeight};
  
  /* Border radius */
  --radius-none: ${radius.none};
  --radius-sm: ${radius.sm};
  --radius-md: ${radius.md};
  --radius-lg: ${radius.lg};
  --radius-xl: ${radius.xl};
  --radius-2xl: ${radius['2xl']};
  --radius-full: ${radius.full};
  
  /* Shadows */
  --shadow-none: ${shadow.none};
  --shadow-xs: ${shadow.xs};
  --shadow-sm: ${shadow.sm};
  --shadow-md: ${shadow.md};
  --shadow-lg: ${shadow.lg};
  --shadow-card: ${shadow.card};
  --shadow-dropdown: ${shadow.dropdown};
  --shadow-modal: ${shadow.modal};
  --shadow-focus-ring: ${shadow.focusRing};
}
`;


// =============================================================================
// SECTION 6: COMPONENT STYLE PRESETS
// =============================================================================
/**
 * Pre-built style objects for common components
 * Use with MUI sx prop or styled-components
 */

export const componentStyles = {
  // Page container
  pageContainer: {
    maxWidth: layoutSpacing.pageMaxWidth,
    marginX: 'auto',
    paddingX: layoutSpacing.pagePaddingX,
    paddingY: layoutSpacing.pagePaddingY,
    backgroundColor: colors.bg.page,
    minHeight: '100vh',
  },
  
  // Card base
  card: {
    backgroundColor: colors.bg.card,
    border: `1px solid ${colors.border.default}`,
    borderRadius: radius.lg,
    padding: layoutSpacing.cardPadding,
  },
  
  // Card hoverable
  cardHoverable: {
    backgroundColor: colors.bg.card,
    border: `1px solid ${colors.border.default}`,
    borderRadius: radius.lg,
    padding: layoutSpacing.cardPadding,
    transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
    cursor: 'pointer',
    '&:hover': {
      borderColor: colors.border.strong,
      boxShadow: shadow.cardHover,
    },
  },
  
  // Table container
  tableContainer: {
    backgroundColor: colors.bg.card,
    border: `1px solid ${colors.border.default}`,
    borderRadius: radius.lg,
    overflow: 'hidden',
  },
  
  // Table header cell
  tableHeaderCell: {
    ...typography.tableHeader,
    color: colors.text.primary,
    backgroundColor: colors.bg.tableHeader,
    borderBottom: `1px solid ${colors.border.default}`,
    paddingX: layoutSpacing.tableCellPaddingX,
    paddingY: layoutSpacing.tableHeaderPaddingY,
  },
  
  // Table body cell
  tableBodyCell: {
    ...typography.tableCell,
    color: colors.text.primary,
    borderBottom: `1px solid ${colors.border.light}`,
    paddingX: layoutSpacing.tableCellPaddingX,
    paddingY: layoutSpacing.tableCellPaddingY,
  },
  
  // Table row hover
  tableRowHover: {
    transition: 'background-color 0.15s ease',
    '&:hover': {
      backgroundColor: colors.bg.tableRowHover,
    },
  },
  
  // Badge base
  badge: {
    ...typography.caption,
    display: 'inline-flex',
    alignItems: 'center',
    paddingX: layoutSpacing.badgePaddingX,
    paddingY: layoutSpacing.badgePaddingY,
    borderRadius: radius.md,
    border: '1px solid',
  },
  
  // Primary button
  buttonPrimary: {
    ...typography.bodySmall,
    fontWeight: fontWeight.medium,
    backgroundColor: colors.brand.primary,
    color: colors.text.inverse,
    borderRadius: radius.md,
    paddingX: layoutSpacing.buttonPaddingX,
    paddingY: layoutSpacing.buttonPaddingY,
    border: 'none',
    cursor: 'pointer',
    transition: 'background-color 0.15s ease',
    '&:hover': {
      backgroundColor: colors.brand.primaryHover,
    },
    '&:focus': {
      outline: 'none',
      boxShadow: shadow.focusRing,
    },
  },
  
  // Secondary button
  buttonSecondary: {
    ...typography.bodySmall,
    fontWeight: fontWeight.medium,
    backgroundColor: colors.bg.card,
    color: colors.text.primary,
    borderRadius: radius.md,
    paddingX: layoutSpacing.buttonPaddingX,
    paddingY: layoutSpacing.buttonPaddingY,
    border: `1px solid ${colors.border.default}`,
    cursor: 'pointer',
    transition: 'background-color 0.15s ease, border-color 0.15s ease',
    '&:hover': {
      backgroundColor: colors.bg.muted,
      borderColor: colors.border.strong,
    },
    '&:focus': {
      outline: 'none',
      boxShadow: shadow.focusRing,
    },
  },
  
  // Input
  input: {
    ...typography.body,
    height: layoutSpacing.inputHeight,
    backgroundColor: colors.bg.input,
    color: colors.text.primary,
    borderRadius: radius.md,
    border: `1px solid ${colors.border.default}`,
    paddingX: spacing[3],
    transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
    '&:hover': {
      borderColor: colors.border.strong,
    },
    '&:focus': {
      outline: 'none',
      borderColor: colors.border.focus,
      boxShadow: shadow.focusRing,
    },
    '&::placeholder': {
      color: colors.text.placeholder,
    },
  },
  
  // Link
  link: {
    color: colors.text.link,
    textDecoration: 'none',
    '&:hover': {
      color: colors.text.linkHover,
      textDecoration: 'underline',
    },
  },
  
  // Muted timestamp
  timestamp: {
    ...typography.metadata,
    color: colors.text.muted,
  },
  
  // Monospace ID
  monoId: {
    ...typography.mono,
    color: colors.text.link,
  },
};


// =============================================================================
// DEFAULT EXPORT
// =============================================================================

export const globalDesignSystem = {
  fontFamily,
  fontSize,
  fontWeight,
  lineHeight,
  letterSpacing,
  typography,
  spacing,
  layoutSpacing,
  colors,
  radius,
  shadow,
  elevation,
  componentStyles,
  cssVariables,
};

export default globalDesignSystem;
