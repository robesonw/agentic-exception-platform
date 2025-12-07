import { Alert } from '@mui/material'
import type { CommonConfigFilters } from './DomainPacksList.tsx'

/**
 * Props for TenantPoliciesList component
 */
export interface TenantPoliciesListProps {
  filters: CommonConfigFilters
  onSelectItem: (type: 'domain-packs' | 'tenant-policies' | 'playbooks', id: string) => void
}

/**
 * Tenant Policies List Component
 * 
 * Note: Backend does not currently provide a list endpoint for tenant policies.
 * This component shows a placeholder message.
 * 
 * TODO: When backend adds GET /admin/config/tenant-policies endpoint, implement full list view.
 */
export default function TenantPoliciesList({ filters: _filters, onSelectItem: _onSelectItem }: TenantPoliciesListProps) {
  return (
    <Alert severity="info">
      Tenant Policy Packs list view is not yet available. The backend does not currently provide a list endpoint for tenant policies.
      <br />
      <br />
      To view a specific tenant policy, use the detail endpoint: <code>GET /admin/config/tenant-policies/&#123;config_id&#125;</code>
      <br />
      <br />
      Format: <code>tenant_id:domain</code> (e.g., <code>tenant_001:Finance</code>)
    </Alert>
  )
}

