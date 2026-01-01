/**
 * ═══════════════════════════════════════════════════════════════════════════════
 * SENTINAI THEME - UNIFIED EXPORT
 * ═══════════════════════════════════════════════════════════════════════════════
 * 
 * Import the complete design system from this single entry point:
 * 
 *   import { colors, typography, spacing, ... } from '@/theme'
 * 
 * For CSS variables, import the global stylesheet in main.tsx:
 * 
 *   import '@/theme/globalStyles.css'
 * 
 */

// MUI Theme (for ThemeProvider)
export { defaultTheme, createAppTheme, themeColors } from './theme'

// Legacy tokens (for backward compatibility during migration)
export { 
  default as tokens, 
  lightColors, 
  darkColors, 
  severityColors, 
  statusColors, 
  spacing, 
  radii, 
  shadows, 
  typography, 
  typographyScale, 
  layout, 
  breakpoints 
} from './tokens'

// New Global Design System (preferred for new components)
export {
  // Typography
  fontFamily,
  fontSize,
  fontWeight,
  lineHeight,
  letterSpacing,
  typography as typographySystem,
  
  // Spacing
  spacing as spacingScale,
  layoutSpacing,
  
  // Colors
  colors,
  
  // Elevation
  radius,
  shadow,
  elevation,
  
  // Pre-built component styles
  componentStyles,
  
  // CSS variables string (for injection)
  cssVariables,
  
  // Full system export
  globalDesignSystem,
} from './globalDesignSystem'


