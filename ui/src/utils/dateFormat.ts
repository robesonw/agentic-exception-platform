/**
 * Shared date/time formatting utilities
 * 
 * Provides consistent date and datetime formatting across the application.
 * All functions handle null/undefined values gracefully.
 */

/**
 * Format a date value to "YYYY-MM-DD" format
 * 
 * @param value Date string (ISO format), Date object, or null/undefined
 * @returns Formatted date string "YYYY-MM-DD" or "-" if invalid/null
 */
export function formatDate(value: string | Date | null | undefined): string {
  if (!value) {
    return '-'
  }

  try {
    const date = typeof value === 'string' ? new Date(value) : value
    
    // Check if date is valid
    if (isNaN(date.getTime())) {
      return '-'
    }

    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')

    return `${year}-${month}-${day}`
  } catch {
    return '-'
  }
}

/**
 * Format a datetime value to "YYYY-MM-DD HH:mm:ss" format (24-hour, local time)
 * 
 * @param value Date string (ISO format), Date object, or null/undefined
 * @returns Formatted datetime string "YYYY-MM-DD HH:mm:ss" or "-" if invalid/null
 */
export function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) {
    return '-'
  }

  try {
    const date = typeof value === 'string' ? new Date(value) : value
    
    // Check if date is valid
    if (isNaN(date.getTime())) {
      return '-'
    }

    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    const seconds = String(date.getSeconds()).padStart(2, '0')

    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
  } catch {
    return '-'
  }
}

/**
 * Format a datetime value to a human-readable relative time string
 *
 * Examples: "just now", "5 minutes ago", "2 hours ago", "yesterday", "3 days ago"
 *
 * @param value Date string (ISO format), Date object, or null/undefined
 * @returns Relative time string or "-" if invalid/null
 */
export function formatRelativeTime(value: string | Date | null | undefined): string {
  if (!value) {
    return '-'
  }

  try {
    const date = typeof value === 'string' ? new Date(value) : value

    // Check if date is valid
    if (isNaN(date.getTime())) {
      return '-'
    }

    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffSeconds = Math.floor(diffMs / 1000)
    const diffMinutes = Math.floor(diffSeconds / 60)
    const diffHours = Math.floor(diffMinutes / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffSeconds < 60) {
      return 'just now'
    } else if (diffMinutes < 60) {
      return diffMinutes === 1 ? '1 minute ago' : `${diffMinutes} minutes ago`
    } else if (diffHours < 24) {
      return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`
    } else if (diffDays === 1) {
      return 'yesterday'
    } else if (diffDays < 7) {
      return `${diffDays} days ago`
    } else if (diffDays < 30) {
      const weeks = Math.floor(diffDays / 7)
      return weeks === 1 ? '1 week ago' : `${weeks} weeks ago`
    } else if (diffDays < 365) {
      const months = Math.floor(diffDays / 30)
      return months === 1 ? '1 month ago' : `${months} months ago`
    } else {
      const years = Math.floor(diffDays / 365)
      return years === 1 ? '1 year ago' : `${years} years ago`
    }
  } catch {
    return '-'
  }
}

