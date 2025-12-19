/**
 * Tests for Admin API client
 * 
 * P11-21: Tests for admin API functions and error handling
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as adminApi from '../admin'
import { httpClient } from '../utils/httpClient.ts'

// Mock httpClient
vi.mock('../utils/httpClient', () => ({
  httpClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('Admin API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('listConfigChanges', () => {
    it('calls correct endpoint with params', async () => {
      const mockResponse = {
        items: [],
        total: 0,
      }
      vi.mocked(httpClient.get).mockResolvedValue(mockResponse)

      await adminApi.listConfigChanges({
        tenantId: 'test-tenant',
        status: 'pending',
        limit: 50,
        offset: 0,
      })

      expect(httpClient.get).toHaveBeenCalledWith('/admin/config-changes', {
        params: {
          tenant_id: 'test-tenant',
          status: 'pending',
          limit: 50,
          offset: 0,
        },
      })
    })

    it('transforms response correctly', async () => {
      const mockResponse = {
        items: [
          {
            id: 'change-1',
            tenant_id: 'test-tenant',
            change_type: 'domain_pack',
            resource_id: 'pack-1',
            status: 'pending',
            requested_by: 'user@example.com',
            requested_at: '2024-01-01T00:00:00Z',
          },
        ],
        total: 1,
      }
      vi.mocked(httpClient.get).mockResolvedValue(mockResponse)

      const result = await adminApi.listConfigChanges({ tenantId: 'test-tenant' })

      expect(result.items).toHaveLength(1)
      expect(result.items[0].id).toBe('change-1')
      expect(result.items[0].tenantId).toBe('test-tenant')
      expect(result.items[0].changeType).toBe('domain_pack')
      expect(result.total).toBe(1)
    })
  })

  describe('approveConfigChange', () => {
    it('calls correct endpoint with comment', async () => {
      vi.mocked(httpClient.post).mockResolvedValue(undefined)

      await adminApi.approveConfigChange('change-1', 'test-tenant', 'Looks good')

      expect(httpClient.post).toHaveBeenCalledWith(
        '/admin/config-changes/change-1/approve',
        { comment: 'Looks good' },
        {
          params: { tenant_id: 'test-tenant' },
        }
      )
    })
  })

  describe('rejectConfigChange', () => {
    it('calls correct endpoint with comment', async () => {
      vi.mocked(httpClient.post).mockResolvedValue(undefined)

      await adminApi.rejectConfigChange('change-1', 'test-tenant', 'Invalid config')

      expect(httpClient.post).toHaveBeenCalledWith(
        '/admin/config-changes/change-1/reject',
        { comment: 'Invalid config' },
        {
          params: { tenant_id: 'test-tenant' },
        }
      )
    })
  })

  describe('getRateLimits', () => {
    it('calls correct endpoint', async () => {
      const mockResponse = {
        limits: [
          {
            tenant_id: 'test-tenant',
            limit_type: 'api_requests',
            limit_value: 1000,
            window_seconds: 60,
            enabled: true,
          },
        ],
      }
      vi.mocked(httpClient.get).mockResolvedValue(mockResponse)

      const result = await adminApi.getRateLimits('test-tenant')

      expect(httpClient.get).toHaveBeenCalledWith('/admin/rate-limits/test-tenant')
      expect(result).toHaveLength(1)
      expect(result[0].tenantId).toBe('test-tenant')
      expect(result[0].limitType).toBe('api_requests')
    })
  })

  describe('listDomainPacks', () => {
    it('calls correct endpoint with params', async () => {
      const mockResponse = {
        items: [],
        total: 0,
      }
      vi.mocked(httpClient.get).mockResolvedValue(mockResponse)

      await adminApi.listDomainPacks({
        tenantId: 'test-tenant',
        domain: 'finance',
        limit: 25,
        offset: 0,
      })

      expect(httpClient.get).toHaveBeenCalledWith('/admin/config/domain-packs', {
        params: {
          tenant_id: 'test-tenant',
          domain: 'finance',
          limit: 25,
          offset: 0,
        },
      })
    })
  })

  describe('activatePlaybook', () => {
    it('calls correct endpoint', async () => {
      vi.mocked(httpClient.post).mockResolvedValue(undefined)

      await adminApi.activatePlaybook('playbook-1', 'test-tenant', true)

      expect(httpClient.post).toHaveBeenCalledWith(
        '/admin/config/playbooks/playbook-1/activate',
        { active: true },
        {
          params: { tenant_id: 'test-tenant' },
        }
      )
    })
  })

  describe('enableToolForTenant', () => {
    it('calls correct endpoint', async () => {
      vi.mocked(httpClient.post).mockResolvedValue(undefined)

      await adminApi.enableToolForTenant('tool-1', 'test-tenant', true)

      expect(httpClient.post).toHaveBeenCalledWith(
        '/api/tools/tool-1/enable',
        { enabled: true },
        {
          params: { tenant_id: 'test-tenant' },
        }
      )
    })
  })
})

