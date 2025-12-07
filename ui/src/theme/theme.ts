import { createTheme, Theme } from '@mui/material/styles'

// Define theme options for light mode
const lightThemeOptions = {
  palette: {
    mode: 'light' as const,
    primary: {
      main: '#1976d2', // Calm blue
      light: '#42a5f5',
      dark: '#1565c0',
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

// Define theme options for dark mode
const darkThemeOptions = {
  palette: {
    mode: 'dark' as const,
    primary: {
      main: '#90caf9', // Light blue
      light: '#e3f2fd',
      dark: '#42a5f5',
      contrastText: '#000',
    },
    secondary: {
      main: '#4db6ac', // Teal - matching light theme
      light: '#80cbc4',
      dark: '#00897b',
      contrastText: '#000',
    },
    background: {
      default: '#121212',
      paper: '#1e1e1e',
    },
    text: {
      primary: '#fff',
      secondary: 'rgba(255, 255, 255, 0.7)',
    },
  },
  typography: {
    ...lightThemeOptions.typography,
  },
  spacing: 8,
  shape: {
    borderRadius: 8, // Match light theme
  },
  components: {
    ...lightThemeOptions.components,
  },
}

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

// Export default light theme
export const defaultTheme = createAppTheme('light')

