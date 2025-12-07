/**
 * Hook to set document title dynamically
 * 
 * Sets the browser tab title to: `${title} | Agentic Exception Platform`
 * Restores default title on unmount.
 */

import { useEffect } from 'react'

const DEFAULT_TITLE = 'Agentic Exception Platform'

/**
 * Sets the document title with a consistent format
 * 
 * @param title The page-specific title (e.g., "Exceptions", "Exception 123")
 */
export function useDocumentTitle(title: string) {
  useEffect(() => {
    const previousTitle = document.title
    
    // Set new title
    document.title = title ? `${title} | ${DEFAULT_TITLE}` : DEFAULT_TITLE
    
    // Cleanup: restore previous title on unmount
    return () => {
      document.title = previousTitle
    }
  }, [title])
}

