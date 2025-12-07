/**
 * Common API types and primitives
 * 
 * These types are used across all API endpoints for consistent request/response handling.
 * Mirrors backend API patterns from src/api/routes/*.py
 */

/**
 * Pagination parameters for list endpoints
 * Mirrors pagination query parameters in router_operator.py and router_explanations.py
 */
export interface PaginationParams {
  /** Page number (1-indexed) */
  page: number
  /** Number of items per page */
  pageSize: number
  /** Optional field to sort by */
  sortField?: string
  /** Sort direction */
  sortDirection?: 'asc' | 'desc'
}

/**
 * Paginated response wrapper
 * Mirrors ExceptionListResponse, ExplanationSearchResponse, ConfigListResponse patterns
 */
export interface PaginatedResponse<T> {
  /** Array of items for current page */
  items: T[]
  /** Total number of items across all pages */
  total: number
  /** Current page number (1-indexed) */
  page: number
  /** Number of items per page */
  pageSize: number
  /** Total number of pages */
  totalPages: number
}

/**
 * Error response shape from backend
 * Mirrors FastAPI HTTPException and error responses
 */
export interface ErrorResponse {
  /** Error message */
  detail: string
  /** Optional error code */
  code?: string
  /** Optional additional error details */
  details?: unknown
}

/**
 * Standard API response wrapper
 * Used for non-paginated endpoints
 */
export interface ApiResponse<T> {
  /** Response data */
  data: T
}

