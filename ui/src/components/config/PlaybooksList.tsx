import { Alert } from '@mui/material'
import type { CommonConfigFilters } from './DomainPacksList.tsx'

/**
 * Props for PlaybooksList component
 */
export interface PlaybooksListProps {
  filters: CommonConfigFilters
  onSelectItem: (type: 'domain-packs' | 'tenant-policies' | 'playbooks', id: string) => void
}

/**
 * Playbooks List Component
 * 
 * Note: Backend does not currently provide a list endpoint for playbooks.
 * This component shows a placeholder message.
 * 
 * TODO: When backend adds GET /admin/config/playbooks endpoint, implement full list view.
 */
export default function PlaybooksList({ filters: _filters, onSelectItem: _onSelectItem }: PlaybooksListProps) {
  return (
    <Alert severity="info">
      Playbooks list view is not yet available. The backend does not currently provide a list endpoint for playbooks.
      <br />
      <br />
      To view a specific playbook, use the detail endpoint: <code>GET /admin/config/playbooks/&#123;config_id&#125;</code>
      <br />
      <br />
      Format: <code>tenant_id:domain:exception_type</code> (e.g., <code>tenant_001:Finance:PaymentFailed</code>)
    </Alert>
  )
}

