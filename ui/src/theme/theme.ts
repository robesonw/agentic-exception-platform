import { createTheme, Theme } from '@mui/material/styles'

// Import design system tokens for consistency
import { fontFamily, colors as dsColors } from './globalDesignSystem'

// Enterprise dark theme color palette (inspired by modern SaaS dashboards)
// Uses sidebar-style colors - NOT pure black for enterprise calm aesthetic
const darkColors = {
  // Background colors (sidebar-inspired, not pure black)
  bgPrimary: '#0f172a',      // Main background (slate-900, not black)
  bgSecondary: '#1e293b',    // Cards, surfaces (slate-800)
  bgTertiary: '#334155',     // Elevated surfaces (slate-700)
  bgElevated: '#475569',     // Hover states (slate-600)
  bgMuted: '#1e293b',        // Muted backgrounds
  bgTableHeader: '#1e293b',  // Table header background
  bgTableRowHover: 'rgba(71, 85, 105, 0.3)', // Row hover (subtle)
  
  // Border colors
  borderPrimary: 'rgba(148, 163, 184, 0.15)',   // Subtle borders
  borderSecondary: 'rgba(148, 163, 184, 0.25)', // More visible borders
  borderAccent: 'rgba(37, 99, 235, 0.3)',       // Primary accent borders
  
  // Text colors
  textPrimary: '#e5e7eb',        // Primary text (gray-200)
  textSecondary: '#9ca3af',      // Secondary text (gray-400)
  textTertiary: '#6b7280',       // Tertiary text (gray-500)
  textMuted: '#6b7280',          // Muted text
  textPlaceholder: '#6b7280',    // Placeholder text
  
  // Accent colors
  primary: '#3b82f6',         // Blue (muted primary actions)
  primaryLight: '#60a5fa',    // Lighter blue
  primaryDark: '#2563eb',     // Darker blue
  primaryGlow: 'rgba(59, 130, 246, 0.3)', // Glow effect
  
  // Status colors (muted for enterprise calm)
  success: '#22c55e',         // Green (success, resolved)
  successDark: '#16a34a',
  warning: '#eab308',         // Yellow (warnings) - muted
  error: '#ef4444',           // Red (errors, critical)
  info: '#3b82f6',            // Blue (info)
  
  // Severity colors (muted, not neon)
  critical: '#ef4444',        // Critical severity - muted red
  high: '#f97316',            // High severity - muted orange
  medium: '#eab308',          // Medium severity - muted yellow
  low: '#22c55e',             // Low severity - muted green
}

// Define theme options for light mode (using design system tokens)
const lightThemeOptions = {
  palette: {
    mode: 'light' as const,
    primary: {
      main: dsColors.brand.primary,
      light: dsColors.brand.primaryHover,
      dark: dsColors.brand.primaryActive,
      contrastText: '#fff',
    },
    secondary: {
      main: '#00897b', // Teal - complementary accent
      light: '#4db6ac',
      dark: '#00695c',
      contrastText: '#fff',
    },
    background: {
      default: dsColors.bg.app,
      paper: dsColors.bg.card,
    },
    text: {
      primary: dsColors.text.primary,
      secondary: dsColors.text.secondary,
    },
    divider: dsColors.border.default,
    error: {
      main: dsColors.semantic.error.text,
      light: dsColors.semantic.error.icon,
    },
    warning: {
      main: dsColors.semantic.warning.text,
      light: dsColors.semantic.warning.icon,
    },
    success: {
      main: dsColors.semantic.success.text,
      light: dsColors.semantic.success.icon,
    },
    info: {
      main: dsColors.semantic.info.text,
      light: dsColors.semantic.info.icon,
    },
  },
  typography: {
    fontFamily: fontFamily.primary,
    // Enterprise-style typography using design system scale
    h1: {
      fontSize: '1.75rem',    // 28px - page titles
      fontWeight: 700,
      lineHeight: 1.2,
      letterSpacing: '-0.02em',
      color: dsColors.text.primary,
    },
    h2: {
      fontSize: '1.25rem',    // 20px - large section titles
      fontWeight: 600,
      lineHeight: 1.3,
      letterSpacing: '-0.01em',
      color: dsColors.text.primary,
    },
    h3: {
      fontSize: '1.125rem',   // 18px - section titles
      fontWeight: 600,
      lineHeight: 1.4,
      color: dsColors.text.primary,
    },
    h4: {
      fontSize: '0.9375rem',  // 15px - card titles
      fontWeight: 600,
      lineHeight: 1.4,
      color: dsColors.text.primary,
    },
    h5: {
      fontSize: '0.875rem',   // 14px - subsection headers
      fontWeight: 600,
      lineHeight: 1.5,
      color: dsColors.text.primary,
    },
    h6: {
      fontSize: '0.8125rem',  // 13px - small headers
      fontWeight: 600,
      lineHeight: 1.5,
      color: dsColors.text.primary,
    },
    subtitle1: {
      fontSize: '0.9375rem',  // 15px
      fontWeight: 400,
      lineHeight: 1.5,
      color: dsColors.text.secondary,
    },
    subtitle2: {
      fontSize: '0.8125rem',  // 13px
      fontWeight: 500,
      lineHeight: 1.5,
      color: dsColors.text.secondary,
    },
    body1: {
      fontSize: '0.875rem',   // 14px - body text
      fontWeight: 400,
      lineHeight: 1.5,
      color: dsColors.text.primary,
    },
    body2: {
      fontSize: '0.8125rem',  // 13px - small body text
      fontWeight: 400,
      lineHeight: 1.5,
      color: dsColors.text.primary,
    },
    caption: {
      fontSize: '0.75rem',    // 12px - captions/metadata
      fontWeight: 400,
      lineHeight: 1.4,
      color: dsColors.text.muted,
    },
    overline: {
      fontSize: '0.75rem',    // 12px - labels
      fontWeight: 600,
      lineHeight: 1.4,
      letterSpacing: '0.05em',
      textTransform: 'uppercase' as const,
      color: dsColors.text.muted,
    },
    button: {
      fontSize: '0.8125rem',  // 13px
      fontWeight: 500,
      lineHeight: 1.5,
      textTransform: 'none' as const,
    },
  },
  spacing: 8, // Baseline spacing unit (8px)
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        html: {
          WebkitFontSmoothing: 'antialiased',
          MozOsxFontSmoothing: 'grayscale',
        },
        body: {
          backgroundColor: dsColors.bg.app,
          color: dsColors.text.primary,
        },
        '*, *::before, *::after': {
          boxSizing: 'border-box',
        },
      },
    },
    MuiButton: {
      defaultProps: {
        size: 'medium' as const,
        disableElevation: true,
      },
      styleOverrides: {
        root: {
          borderRadius: 6,
          textTransform: 'none',
          fontWeight: 500,
          fontSize: '0.8125rem',
          padding: '8px 16px',
          minHeight: 36,
        },
        contained: {
          boxShadow: 'none',
          '&:hover': {
            boxShadow: 'none',
          },
        },
        outlined: {
          borderColor: dsColors.border.default,
          '&:hover': {
            borderColor: dsColors.border.strong,
            backgroundColor: dsColors.bg.muted,
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          border: `1px solid ${dsColors.border.default}`,
          boxShadow: 'none',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          backgroundImage: 'none',
        },
        elevation0: {
          boxShadow: 'none',
        },
        elevation1: {
          boxShadow: 'none',
          border: `1px solid ${dsColors.border.default}`,
        },
      },
    },
    MuiTable: {
      defaultProps: {
        size: 'small' as const,
      },
    },
    MuiTableContainer: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          border: `1px solid ${dsColors.border.default}`,
          overflow: 'hidden',
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          padding: '12px 16px',
          borderBottom: `1px solid ${dsColors.border.light}`,
          fontSize: '0.8125rem',
          lineHeight: 1.5,
        },
        head: {
          fontWeight: 600,
          fontSize: '0.8125rem',
          color: dsColors.text.primary,
          backgroundColor: dsColors.bg.tableHeader,
          borderBottom: `1px solid ${dsColors.border.default}`,
          whiteSpace: 'nowrap',
        },
        body: {
          color: dsColors.text.primary,
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          height: 44, // Standard row height from design system
          '&:last-child td': {
            borderBottom: 0,
          },
          '&:hover': {
            backgroundColor: dsColors.bg.tableRowHover,
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 6,
          fontWeight: 500,
          fontSize: '0.75rem',
          height: 24,
        },
        sizeSmall: {
          height: 20,
          fontSize: '0.6875rem',
        },
      },
    },
    MuiTextField: {
      defaultProps: {
        size: 'small' as const,
      },
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            fontSize: '0.875rem',
            borderRadius: 6,
            '& fieldset': {
              borderColor: dsColors.border.default,
            },
            '&:hover fieldset': {
              borderColor: dsColors.border.strong,
            },
            '&.Mui-focused fieldset': {
              borderColor: dsColors.brand.primary,
              borderWidth: 1,
            },
          },
          '& .MuiInputBase-input': {
            padding: '10px 12px',
          },
        },
      },
    },
    MuiSelect: {
      defaultProps: {
        size: 'small' as const,
      },
      styleOverrides: {
        root: {
          fontSize: '0.875rem',
          borderRadius: 6,
        },
      },
    },
    MuiInputBase: {
      styleOverrides: {
        root: {
          fontSize: '0.875rem',
        },
        input: {
          '&::placeholder': {
            color: dsColors.text.placeholder,
            opacity: 1,
          },
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: 12,
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
        },
      },
    },
    MuiDialogTitle: {
      styleOverrides: {
        root: {
          fontSize: '1.125rem',
          fontWeight: 600,
          padding: '20px 24px 12px',
        },
      },
    },
    MuiDialogContent: {
      styleOverrides: {
        root: {
          padding: '12px 24px 20px',
        },
      },
    },
    MuiDialogActions: {
      styleOverrides: {
        root: {
          padding: '12px 24px 20px',
        },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          fontSize: '0.75rem',
          backgroundColor: dsColors.neutral[800],
          borderRadius: 6,
          padding: '6px 10px',
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          fontSize: '0.8125rem',
        },
        standardSuccess: {
          backgroundColor: dsColors.semantic.success.bg,
          color: dsColors.semantic.success.text,
          border: `1px solid ${dsColors.semantic.success.border}`,
        },
        standardWarning: {
          backgroundColor: dsColors.semantic.warning.bg,
          color: dsColors.semantic.warning.text,
          border: `1px solid ${dsColors.semantic.warning.border}`,
        },
        standardError: {
          backgroundColor: dsColors.semantic.error.bg,
          color: dsColors.semantic.error.text,
          border: `1px solid ${dsColors.semantic.error.border}`,
        },
        standardInfo: {
          backgroundColor: dsColors.semantic.info.bg,
          color: dsColors.semantic.info.text,
          border: `1px solid ${dsColors.semantic.info.border}`,
        },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: {
          borderRadius: 4,
          height: 6,
          backgroundColor: dsColors.bg.muted,
        },
      },
    },
    MuiTabs: {
      styleOverrides: {
        root: {
          minHeight: 40,
        },
        indicator: {
          height: 2,
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 500,
          fontSize: '0.875rem',
          minHeight: 40,
          padding: '8px 16px',
        },
      },
    },
    MuiBreadcrumbs: {
      styleOverrides: {
        root: {
          fontSize: '0.8125rem',
        },
        separator: {
          color: dsColors.text.muted,
        },
      },
    },
    MuiLink: {
      styleOverrides: {
        root: {
          color: dsColors.text.link,
          textDecoration: 'none',
          '&:hover': {
            color: dsColors.text.linkHover,
            textDecoration: 'underline',
          },
        },
      },
    },
  },
}

// Define theme options for dark mode (enterprise-grade dark theme)
// Uses sidebar-style colors, NOT pure black, for enterprise calm
const darkThemeOptions = {
  palette: {
    mode: 'dark' as const,
    primary: {
      main: darkColors.primary,
      light: darkColors.primaryLight,
      dark: darkColors.primaryDark,
      contrastText: '#fff',
    },
    secondary: {
      main: darkColors.success,
      light: '#34d399',
      dark: darkColors.successDark,
      contrastText: '#000',
    },
    error: {
      main: darkColors.error,
      light: '#f87171',
      dark: '#dc2626',
      contrastText: '#fff',
    },
    warning: {
      main: darkColors.warning,
      light: '#fbbf24',
      dark: '#d97706',
      contrastText: '#000',
    },
    info: {
      main: darkColors.info,
      light: '#60a5fa',
      dark: '#2563eb',
      contrastText: '#fff',
    },
    success: {
      main: darkColors.success,
      light: '#34d399',
      dark: darkColors.successDark,
      contrastText: '#000',
    },
    background: {
      default: darkColors.bgPrimary,
      paper: darkColors.bgSecondary,
    },
    text: {
      primary: darkColors.textPrimary,
      secondary: darkColors.textSecondary,
      disabled: darkColors.textTertiary,
    },
    divider: darkColors.borderPrimary,
    action: {
      hover: 'rgba(148, 163, 184, 0.08)',
      selected: 'rgba(148, 163, 184, 0.16)',
      disabled: 'rgba(148, 163, 184, 0.3)',
      disabledBackground: 'rgba(148, 163, 184, 0.12)',
    },
  },
  typography: {
    fontFamily: fontFamily.primary, // Use Inter from design system
    h1: {
      fontSize: '1.75rem',
      fontWeight: 700,
      lineHeight: 1.2,
      letterSpacing: '-0.02em',
    },
    h2: {
      fontSize: '1.25rem',
      fontWeight: 600,
      lineHeight: 1.3,
      letterSpacing: '-0.01em',
    },
    h3: {
      fontSize: '1.125rem',
      fontWeight: 600,
      lineHeight: 1.4,
    },
    h4: {
      fontSize: '0.9375rem',
      fontWeight: 600,
      lineHeight: 1.4,
    },
    h5: {
      fontSize: '0.875rem',
      fontWeight: 600,
      lineHeight: 1.5,
    },
    h6: {
      fontSize: '0.8125rem',
      fontWeight: 600,
      lineHeight: 1.5,
    },
    subtitle1: {
      fontSize: '0.9375rem',
      fontWeight: 400,
      lineHeight: 1.5,
    },
    subtitle2: {
      fontSize: '0.8125rem',
      fontWeight: 500,
      lineHeight: 1.5,
    },
    body1: {
      fontSize: '0.875rem',
      fontWeight: 400,
      lineHeight: 1.5,
    },
    body2: {
      fontSize: '0.8125rem',
      fontWeight: 400,
      lineHeight: 1.5,
    },
    caption: {
      fontSize: '0.75rem',
      fontWeight: 400,
      lineHeight: 1.4,
    },
    overline: {
      fontSize: '0.75rem',
      fontWeight: 600,
      lineHeight: 1.4,
      letterSpacing: '0.05em',
      textTransform: 'uppercase' as const,
    },
    button: {
      fontSize: '0.8125rem',
      fontWeight: 500,
      lineHeight: 1.5,
      textTransform: 'none' as const,
    },
  },
  spacing: 8,
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        html: {
          WebkitFontSmoothing: 'antialiased',
          MozOsxFontSmoothing: 'grayscale',
        },
        body: {
          backgroundColor: darkColors.bgPrimary,
          // No gradient - clean slate background for enterprise calm
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundColor: darkColors.bgSecondary,
          border: `1px solid ${darkColors.borderPrimary}`,
          borderRadius: 8,
          boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.2), 0 1px 2px 0 rgba(0, 0, 0, 0.12)',
        },
        elevation1: {
          boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.2), 0 1px 2px 0 rgba(0, 0, 0, 0.12)',
        },
        elevation2: {
          boxShadow: '0 3px 6px 0 rgba(0, 0, 0, 0.2), 0 2px 4px 0 rgba(0, 0, 0, 0.12)',
        },
        elevation4: {
          boxShadow: '0 6px 12px 0 rgba(0, 0, 0, 0.25), 0 4px 8px 0 rgba(0, 0, 0, 0.15)',
        },
      },
    },
    MuiButton: {
      defaultProps: {
        disableElevation: true,
      },
      styleOverrides: {
        root: {
          borderRadius: 6,
          textTransform: 'none',
          fontWeight: 500,
          fontSize: '0.8125rem',
          padding: '8px 16px',
          minHeight: 36,
          boxShadow: 'none',
          '&:hover': {
            boxShadow: '0 2px 8px 0 rgba(37, 99, 235, 0.2)',
          },
        },
        contained: {
          '&:hover': {
            boxShadow: '0 4px 12px 0 rgba(37, 99, 235, 0.3)',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: darkColors.bgSecondary,
          border: `1px solid ${darkColors.borderPrimary}`,
          borderRadius: 8,
        },
      },
    },
    MuiTable: {
      defaultProps: {
        size: 'small' as const,
      },
    },
    MuiTableContainer: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          border: `1px solid ${darkColors.borderPrimary}`,
          overflow: 'hidden',
          backgroundColor: darkColors.bgSecondary,
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          padding: '12px 16px',
          borderColor: darkColors.borderPrimary,
          fontSize: '0.8125rem',
          lineHeight: 1.5,
          backgroundColor: darkColors.bgSecondary,
        },
        head: {
          color: darkColors.textSecondary,
          fontWeight: 600,
          fontSize: '0.8125rem',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          backgroundColor: darkColors.bgTableHeader,
        },
        body: {
          color: darkColors.textPrimary,
          backgroundColor: darkColors.bgSecondary,
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          height: 44,
          backgroundColor: darkColors.bgSecondary,
          '&:hover': {
            backgroundColor: darkColors.bgTableRowHover,
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 6,
          fontWeight: 500,
          fontSize: '0.75rem',
          height: 24,
        },
        sizeSmall: {
          height: 20,
          fontSize: '0.6875rem',
        },
      },
    },
    MuiTextField: {
      defaultProps: {
        size: 'small' as const,
      },
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            fontSize: '0.875rem',
            borderRadius: 6,
            backgroundColor: darkColors.bgTertiary,
            '& fieldset': {
              borderColor: darkColors.borderPrimary,
            },
            '&:hover fieldset': {
              borderColor: darkColors.borderSecondary,
            },
            '&.Mui-focused fieldset': {
              borderColor: darkColors.primary,
              borderWidth: 1,
            },
          },
          '& .MuiInputBase-input': {
            padding: '10px 12px',
          },
        },
      },
    },
    MuiSelect: {
      defaultProps: {
        size: 'small' as const,
      },
      styleOverrides: {
        root: {
          fontSize: '0.875rem',
          borderRadius: 6,
        },
      },
    },
    MuiInputBase: {
      styleOverrides: {
        root: {
          fontSize: '0.875rem',
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: 12,
        },
      },
    },
    MuiDialogTitle: {
      styleOverrides: {
        root: {
          fontSize: '1.125rem',
          fontWeight: 600,
          padding: '20px 24px 12px',
        },
      },
    },
    MuiDialogContent: {
      styleOverrides: {
        root: {
          padding: '12px 24px 20px',
        },
      },
    },
    MuiDialogActions: {
      styleOverrides: {
        root: {
          padding: '12px 24px 20px',
        },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          fontSize: '0.75rem',
          borderRadius: 6,
          padding: '6px 10px',
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          fontSize: '0.8125rem',
        },
      },
    },
    MuiTabs: {
      styleOverrides: {
        root: {
          minHeight: 40,
        },
        indicator: {
          height: 2,
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 500,
          fontSize: '0.875rem',
          minHeight: 40,
          padding: '8px 16px',
        },
      },
    },
  },
}

// Export color constants for use in components
export const themeColors = darkColors

/**
 * Create MUI theme based on mode (light or dark)
 * @param mode - 'light' or 'dark'
 * @returns MUI Theme object
 */
export function createAppTheme(mode: 'light' | 'dark' = 'light'): Theme {
  if (mode === 'dark') {
    return createTheme(darkThemeOptions)
  }
  return createTheme(lightThemeOptions)
}

// Export default light theme (enterprise aesthetic with dark sidebar)
export const defaultTheme = createAppTheme('light')

