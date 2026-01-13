/**
 * Button Component (Wave 1)
 * 
 * A button wrapper with consistent styling.
 * Uses MUI theme tokens for automatic light/dark mode support.
 */

import { Button as MuiButton, type ButtonProps as MuiButtonProps, CircularProgress, useTheme } from '@mui/material'
import { radii, typography as typographyTokens } from '../../theme/tokens'

export interface ButtonProps extends Omit<MuiButtonProps, 'variant'> {
  /** Button variant */
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
  /** Loading state */
  loading?: boolean
}

/**
 * Creates variant styles using theme palette for proper light/dark mode support.
 */
const useVariantStyles = () => {
  const theme = useTheme()
  
  return {
    primary: {
      backgroundColor: theme.palette.primary.main,
      color: theme.palette.primary.contrastText,
      border: 'none',
      '&:hover': {
        backgroundColor: theme.palette.primary.dark,
      },
      '&:disabled': {
        backgroundColor: theme.palette.action.disabledBackground,
        color: theme.palette.action.disabled,
      },
    },
    secondary: {
      backgroundColor: theme.palette.action.hover,
      color: theme.palette.text.primary,
      border: `1px solid ${theme.palette.divider}`,
      '&:hover': {
        backgroundColor: theme.palette.action.selected,
        borderColor: theme.palette.text.secondary,
      },
      '&:disabled': {
        backgroundColor: theme.palette.action.disabledBackground,
        color: theme.palette.action.disabled,
      },
    },
    outline: {
      backgroundColor: 'transparent',
      color: theme.palette.primary.main,
      border: `1px solid ${theme.palette.primary.main}`,
      '&:hover': {
        backgroundColor: theme.palette.primary.main + '14', // 8% opacity
      },
      '&:disabled': {
        color: theme.palette.action.disabled,
        borderColor: theme.palette.divider,
      },
    },
    ghost: {
      backgroundColor: 'transparent',
      color: theme.palette.text.secondary,
      border: 'none',
      '&:hover': {
        backgroundColor: theme.palette.action.hover,
        color: theme.palette.text.primary,
      },
      '&:disabled': {
        color: theme.palette.action.disabled,
      },
    },
    danger: {
      backgroundColor: theme.palette.error.main,
      color: theme.palette.error.contrastText,
      border: 'none',
      '&:hover': {
        backgroundColor: theme.palette.error.dark,
      },
      '&:disabled': {
        backgroundColor: theme.palette.action.disabledBackground,
        color: theme.palette.action.disabled,
      },
    },
  }
}

export default function Button({
  variant = 'primary',
  loading = false,
  disabled,
  children,
  startIcon,
  sx,
  ...props
}: ButtonProps) {
  const theme = useTheme()
  const variantStyles = useVariantStyles()
  const styles = variantStyles[variant]

  return (
    <MuiButton
      disabled={disabled || loading}
      startIcon={loading ? <CircularProgress size={16} color="inherit" /> : startIcon}
      sx={{
        borderRadius: `${radii.md}px`,
        textTransform: 'none',
        fontWeight: typographyTokens.fontWeight.medium,
        fontSize: typographyTokens.fontSize.sm,
        padding: '8px 16px',
        minWidth: 'auto',
        boxShadow: 'none',
        transition: 'all 0.2s ease',
        ...styles,
        '&:focus': {
          outline: 'none',
          boxShadow: `0 0 0 2px ${theme.palette.primary.main}40`,
        },
        ...sx,
      }}
      {...props}
    >
      {children}
    </MuiButton>
  )
}
