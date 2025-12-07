import { useParams, Link } from 'react-router-dom'
import { Box, Button, Alert } from '@mui/material'
import { ArrowBack } from '@mui/icons-material'
import PageHeader from '../components/common/PageHeader.tsx'
import { BreadcrumbsNav } from '../components/common'
import ConfigDetailView, { type ConfigType } from '../components/config/ConfigDetailView.tsx'
import { useDocumentTitle } from '../hooks/useDocumentTitle.ts'

/**
 * Config Detail Page Component
 * 
 * Displays configuration detail view for a specific config item.
 * Route: /config/:type/:id
 */
export default function ConfigDetailPage() {
  const { type, id } = useParams<{ type: string; id: string }>()

  // Validate type parameter
  const validTypes: ConfigType[] = ['domain-packs', 'tenant-policies', 'playbooks']
  const configType = type as ConfigType

  // Get human-readable type name for breadcrumbs (plural)
  const getConfigTypeDisplayName = (t: ConfigType): string => {
    switch (t) {
      case 'domain-packs':
        return 'Domain Packs'
      case 'tenant-policies':
        return 'Tenant Policy Packs'
      case 'playbooks':
        return 'Playbooks'
      default:
        return 'Configuration'
    }
  }

  // Get singular form for page title
  const getConfigTypeSingular = (t: ConfigType): string => {
    switch (t) {
      case 'domain-packs':
        return 'Domain Pack'
      case 'tenant-policies':
        return 'Tenant Policy Pack'
      case 'playbooks':
        return 'Playbook'
      default:
        return 'Configuration'
    }
  }

  // Handle missing or invalid parameters
  if (!type || !id) {
    return (
      <Box>
        <BreadcrumbsNav
          items={[
            { label: 'Config', to: '/config' },
            { label: 'Configuration Not Found' },
          ]}
        />
        <PageHeader
          title="Configuration Not Found"
          subtitle="Configuration type or ID is missing"
        />
        <Alert severity="error" sx={{ mt: 3 }}>
          Invalid configuration URL. Please check the URL and try again.
        </Alert>
        <Button component={Link} to="/config" sx={{ mt: 2 }} startIcon={<ArrowBack />}>
          Back to Config Browser
        </Button>
      </Box>
    )
  }

  // Validate config type
  if (!validTypes.includes(configType)) {
    return (
      <Box>
        <BreadcrumbsNav
          items={[
            { label: 'Config', to: '/config' },
            { label: 'Invalid Configuration Type' },
          ]}
        />
        <PageHeader
          title="Invalid Configuration Type"
          subtitle={`Unknown type: ${type}`}
        />
        <Alert severity="error" sx={{ mt: 3 }}>
          Invalid configuration type: {type}. Must be one of: {validTypes.join(', ')}
        </Alert>
        <Button component={Link} to="/config" sx={{ mt: 2 }} startIcon={<ArrowBack />}>
          Back to Config Browser
        </Button>
      </Box>
    )
  }

  // Decode ID from URL
  const decodedId = decodeURIComponent(id)

  // Set document title
  const typeLabel = getConfigTypeSingular(configType)
  useDocumentTitle(`Config ${typeLabel} – ${decodedId}`)

  return (
    <Box>
      <BreadcrumbsNav
        items={[
          { label: 'Config', to: '/config' },
          { label: getConfigTypeDisplayName(configType) },
          { label: decodedId },
        ]}
      />
      <PageHeader
        title={`${getConfigTypeSingular(configType)}: ${decodedId}`}
        subtitle={`View ${getConfigTypeSingular(configType).toLowerCase()} configuration details`}
      />

      <ConfigDetailView type={configType} id={decodedId} />
    </Box>
  )
}

