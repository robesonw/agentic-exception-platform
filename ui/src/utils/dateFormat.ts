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

