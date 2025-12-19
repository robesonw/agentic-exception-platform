/**
 * User context hook
 * 
 * Phase 7 P7-17: Provides current user context for actor_id in step completion.
 * 
 * For MVP, uses a stub user ID from localStorage or generates a default.
 * In production, this would integrate with authentication system.
 */

import { useMemo } from 'react'

/**
 * Get current user ID for actor_id
 * 
 * For MVP, uses localStorage or generates a default stub user ID.
 * In production, this would come from authentication context.
 */
export function useUser(): { userId: string } {
  const userId = useMemo(() => {
    if (typeof window !== 'undefined') {
      // Try to get from localStorage (could be set by login)
      const storedUserId = localStorage.getItem('userId')
      if (storedUserId) {
        return storedUserId
      }
      
      // Generate a stub user ID if not found
      let stubUserId = localStorage.getItem('stubUserId')
      if (!stubUserId) {
        stubUserId = `user_${Date.now()}`
        localStorage.setItem('stubUserId', stubUserId)
      }
      return stubUserId
    }
    
    // Fallback for SSR
    return 'user_stub'
  }, [])

  return { userId }
}









