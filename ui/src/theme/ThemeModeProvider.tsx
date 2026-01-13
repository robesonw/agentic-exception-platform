/**
 * Theme Mode Provider
 * 
 * Manages light/dark mode toggle for the application.
 * Binary toggle only (no system-mode auto switching).
 * 
 * Features:
 * - Persists mode in localStorage under 'sentinai.themeMode'
 * - Initializes from localStorage only (defaults to 'light')
 * - Memoized context to avoid unnecessary re-renders
 * 
 * Usage:
 *   import { useThemeMode } from './theme/ThemeModeProvider'
 *   const { mode, toggleMode } = useThemeMode()
 */

import React, { createContext, useContext, useState, useEffect, useMemo, useCallback } from 'react'

// =============================================================================
// TYPES
// =============================================================================

export type ThemeMode = 'light' | 'dark'

interface ThemeModeContextValue {
  mode: ThemeMode
  toggleMode: () => void
}

// =============================================================================
// CONSTANTS
// =============================================================================

const STORAGE_KEY = 'sentinai.themeMode'
const DEFAULT_MODE: ThemeMode = 'light'

// =============================================================================
// CONTEXT
// =============================================================================

const ThemeModeContext = createContext<ThemeModeContextValue | undefined>(undefined)

// =============================================================================
// PROVIDER
// =============================================================================

interface ThemeModeProviderProps {
  children: React.ReactNode
}

export function ThemeModeProvider({ children }: ThemeModeProviderProps) {
  // Initialize mode from localStorage (sync, no flicker)
  const [mode, setMode] = useState<ThemeMode>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored === 'light' || stored === 'dark') {
        return stored
      }
    } catch {
      // localStorage not available (SSR, privacy mode, etc.)
    }
    return DEFAULT_MODE
  })

  // Persist mode changes to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, mode)
    } catch {
      // localStorage not available
    }
  }, [mode])

  // Toggle mode function (memoized)
  const toggleMode = useCallback(() => {
    setMode((prev) => (prev === 'light' ? 'dark' : 'light'))
  }, [])

  // Memoize context value to prevent re-renders
  const contextValue = useMemo<ThemeModeContextValue>(
    () => ({
      mode,
      toggleMode,
    }),
    [mode, toggleMode]
  )

  return (
    <ThemeModeContext.Provider value={contextValue}>
      {children}
    </ThemeModeContext.Provider>
  )
}

// =============================================================================
// HOOK
// =============================================================================

export function useThemeMode(): ThemeModeContextValue {
  const context = useContext(ThemeModeContext)
  if (context === undefined) {
    throw new Error('useThemeMode must be used within a ThemeModeProvider')
  }
  return context
}
