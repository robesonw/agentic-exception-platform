import { createTheme, Theme } from '@mui/material/styles'

// Enterprise dark theme color palette (inspired by modern SaaS dashboards)
const darkColors = {
  // Background colors
  bgPrimary: '#0B0E14',      // Main background (very dark blue-gray)
  bgSecondary: '#151A23',   // Sidebar, cards (slightly lighter)
  bgTertiary: '#1a1f2e',    // Elevated surfaces
  bgElevated: '#1e293b',    // Hover states, selected items
  
  // Border colors
  borderPrimary: 'rgba(148, 163, 184, 0.1)',   // Subtle borders
  borderSecondary: 'rgba(148, 163, 184, 0.2)', // More visible borders
  borderAccent: 'rgba(37, 99, 235, 0.3)',      // Primary accent borders
  
  // Text colors
  textPrimary: 'rgba(203, 213, 225, 0.95)',    // Primary text (almost white)
  textSecondary: 'rgba(148, 163, 184, 0.8)',   // Secondary text
  textTertiary: 'rgba(148, 163, 184, 0.6)',    // Tertiary text (labels)
  
  // Accent colors
  primary: '#2563eb',        // Blue (primary actions)
  primaryLight: '#3b82f6',   // Lighter blue
  primaryDark: '#1e40af',    // Darker blue
  primaryGlow: 'rgba(37, 99, 235, 0.39)', // Glow effect
  
  // Status colors
  success: '#10b981',        // Green (success, resolved)
  successDark: '#059669',
  warning: '#f59e0b',        // Orange (warnings)
  error: '#ef4444',          // Red (errors, critical)
  info: '#3b82f6',           // Blue (info)
  
  // Severity colors
  critical: '#dc2626',       // Critical severity
  high: '#ea580c',           // High severity
  medium: '#f59e0b',         // Medium severity
  low: '#84cc16',            // Low severity
}

// Define theme options for light mode (keeping for future use)
const lightThemeOptions = {
  palette: {
    mode: 'light' as const,
    primary: {
      main: darkColors.primary,
      light: darkColors.primaryLight,
      dark: darkColors.primaryDark,
      contrastText: '#fff',
    },
    secondary: {
      main: '#00897b', // Teal - complementary accent
      light: '#4db6ac',
      dark: '#00695c',
      contrastText: '#fff',
    },
    background: {
      default: '#f5f5f5',
      paper: '#ffffff',
    },
    text: {
      primary: 'rgba(0, 0, 0, 0.87)',
      secondary: 'rgba(0, 0, 0, 0.6)',
    },
  },
  typography: {
    fontFamily: [
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      'Roboto',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
    ].join(','),
    // Enterprise-style typography - slightly denser
    h1: {
      fontSize: '2.25rem', // Reduced from 2.5rem
      fontWeight: 600, // Slightly bolder
      lineHeight: 1.2,
      letterSpacing: '-0.02em',
    },
    h2: {
      fontSize: '1.875rem', // Reduced from 2rem
      fontWeight: 600,
      lineHeight: 1.3,
      letterSpacing: '-0.01em',
    },
    h3: {
      fontSize: '1.625rem', // Reduced from 1.75rem
      fontWeight: 600,
      lineHeight: 1.4,
    },
    h4: {
      fontSize: '1.375rem', // For page titles
      fontWeight: 600,
      lineHeight: 1.4,
      letterSpacing: '-0.01em',
    },
    h5: {
      fontSize: '1.125rem', // For section headers
      fontWeight: 600,
      lineHeight: 1.5,
    },
    h6: {
      fontSize: '1rem',
      fontWeight: 600,
      lineHeight: 1.6,
    },
    subtitle1: {
      fontSize: '0.9375rem', // Slightly smaller for subtitles
      fontWeight: 400,
      lineHeight: 1.5,
      color: 'rgba(0, 0, 0, 0.6)',
    },
    body1: {
      fontSize: '0.9375rem', // Slightly reduced from 1rem
      lineHeight: 1.5,
    },
    body2: {
      fontSize: '0.8125rem', // Slightly reduced from 0.875rem
      lineHeight: 1.43,
    },
  },
  spacing: 8, // Baseline spacing unit (8px)
  shape: {
    borderRadius: 8, // Increased from 4px for more modern look
  },
  components: {
    MuiButton: {
      defaultProps: {
        size: 'medium' as const,
        variant: 'contained' as const,
      },
      styleOverrides: {
        root: {
          borderRadius: 8,
          textTransform: 'none', // Keep text as-is (no uppercase)
          fontWeight: 500,
          padding: '6px 16px',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
      },
    },
    MuiTable: {
      defaultProps: {
        size: 'small' as const, // Dense tables for enterprise feel
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          padding: '8px 16px', // Denser padding
        },
        head: {
          fontWeight: 600,
          fontSize: '0.8125rem',
        },
      },

    },
  },
}

// Define theme options for dark mode (enterprise-grade dark theme)
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
    },
    divider: darkColors.borderPrimary,
  },
  typography: {
    ...lightThemeOptions.typography,
    fontFamily: [
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      'Roboto',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
    ].join(','),
  },
  spacing: 8,
  shape: {
    borderRadius: 12, // Slightly more rounded for modern feel
  },
  components: {
    ...lightThemeOptions.components,
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: darkColors.bgPrimary,
          backgroundImage: 'radial-gradient(ellipse at top right, rgba(37, 99, 235, 0.15), #0B0E14)',
          backgroundAttachment: 'fixed',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundColor: darkColors.bgSecondary,
          border: `1px solid ${darkColors.borderPrimary}`,
          borderRadius: 12,
          boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.3), 0 1px 2px 0 rgba(0, 0, 0, 0.24)',
        },
        elevation1: {
          boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.3), 0 1px 2px 0 rgba(0, 0, 0, 0.24)',
        },
        elevation2: {
          boxShadow: '0 3px 6px 0 rgba(0, 0, 0, 0.3), 0 2px 4px 0 rgba(0, 0, 0, 0.24)',
        },
        elevation4: {
          boxShadow: '0 6px 12px 0 rgba(0, 0, 0, 0.4), 0 4px 8px 0 rgba(0, 0, 0, 0.3)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          textTransform: 'none',
          fontWeight: 500,
          padding: '8px 20px',
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
          borderRadius: 12,
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderColor: darkColors.borderPrimary,
        },
        head: {
          color: darkColors.textSecondary,
          fontWeight: 600,
          fontSize: '0.8125rem',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        },
        body: {
          color: darkColors.textPrimary,
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:hover': {
            backgroundColor: darkColors.bgTertiary,
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 6,
          fontWeight: 500,
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            backgroundColor: darkColors.bgTertiary,
            '& fieldset': {
              borderColor: darkColors.borderPrimary,
            },
            '&:hover fieldset': {
              borderColor: darkColors.borderSecondary,
            },
            '&.Mui-focused fieldset': {
              borderColor: darkColors.primary,
            },
          },
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

// Export default dark theme (enterprise aesthetic)
export const defaultTheme = createAppTheme('dark')

