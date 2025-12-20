/**
 * Mock data for Playbooks API
 * 
 * Use this in development to test the UI without a backend.
 * 
 * To enable:
 * 1. Import this file in ui/src/api/admin.ts
 * 2. Add a condition to return mock data when USE_MOCK_DATA=true
 */

import type { Playbook } from '../api/admin'
import playbooksData from './playbooks.example.json'

/**
 * Get mock playbooks data
 * Applies filtering based on params to simulate backend behavior
 */
export function getMockPlaybooks(params: {
  tenantId?: string
  domain?: string
  exceptionType?: string
  limit?: number
  offset?: number
} = {}): { items: Playbook[]; total: number } {
  let items = playbooksData.items as Playbook[]

  // Filter by tenant
  if (params.tenantId) {
    items = items.filter((p) => p.tenantId === params.tenantId)
  }

  // Filter by domain
  if (params.domain) {
    items = items.filter((p) => p.domain === params.domain)
  }

  // Filter by exception type
  if (params.exceptionType) {
    items = items.filter((p) => p.exceptionType === params.exceptionType)
  }

  const total = items.length

  // Apply pagination
  const offset = params.offset || 0
  const limit = params.limit || 100
  items = items.slice(offset, offset + limit)

  return {
    items,
    total,
  }
}

/**
 * Get a single mock playbook by ID
 */
export function getMockPlaybook(id: string): Playbook | null {
  const playbook = playbooksData.items.find((p) => p.id === id)
  return playbook as Playbook | null
}

/**
 * Check if mock data should be used
 * Set USE_MOCK_DATA=true in your .env file or environment
 */
export function shouldUseMockData(): boolean {
  return (
    import.meta.env.VITE_USE_MOCK_DATA === 'true' ||
    import.meta.env.MODE === 'development'
  )
}

