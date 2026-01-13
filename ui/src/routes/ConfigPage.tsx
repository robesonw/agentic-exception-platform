import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Box,
  Tabs,
  Tab,
  TextField,
  Grid,
  Typography,
} from '@mui/material'
import DomainPacksList, { type CommonConfigFilters } from '../components/config/DomainPacksList.tsx'
import TenantPoliciesList from '../components/config/TenantPoliciesList.tsx'
import PlaybooksList from '../components/config/PlaybooksList.tsx'
import ConfigRecommendationsTab from '../components/config/ConfigRecommendationsTab.tsx'
import { PageShell, Card } from '../components/ui'
import { useTenant } from '../hooks/useTenant.tsx'
import { useDocumentTitle } from '../hooks/useDocumentTitle.ts'

/**
 * Config type options
 */
type ConfigType = 'domain-packs' | 'tenant-policies' | 'playbooks' | 'recommendations'

/**
 * Tab panel component for tabs content
 */
interface TabPanelProps {
  children?: React.ReactNode
  index: number
  value: number
}

function TabPanel({ children, value, index }: TabPanelProps) {
  return (
    <div role="tabpanel" hidden={value !== index} id={`config-tabpanel-${index}`} aria-labelledby={`config-tab-${index}`}>
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  )
}

/**
 * Config Page Component
 * 
 * Provides a browser interface for viewing Domain Packs, Tenant Policy Packs, and Playbooks.
 * Supports filtering by tenant and domain, and navigation to detail views.
 */
export default function ConfigPage() {
  useDocumentTitle('Config & Learning')
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { tenantId } = useTenant()

  // Get config type from URL or default to 'domain-packs'
  const urlType = searchParams.get('type') as ConfigType | null
  const initialType: ConfigType = urlType && ['domain-packs', 'tenant-policies', 'playbooks', 'recommendations'].includes(urlType)
    ? urlType
    : 'domain-packs'

  const [configType, setConfigType] = useState<ConfigType>(initialType)
  const [tenantFilter, setTenantFilter] = useState<string>(searchParams.get('tenant') || tenantId || '')
  const [domainFilter, setDomainFilter] = useState<string>(searchParams.get('domain') || '')

  // Sync config type with URL
  useEffect(() => {
    if (configType !== urlType) {
      const newParams = new URLSearchParams(searchParams)
      if (configType === 'domain-packs') {
        newParams.delete('type')
      } else {
        newParams.set('type', configType)
      }
      setSearchParams(newParams, { replace: true })
    }
  }, [configType, urlType, searchParams, setSearchParams])

  // Sync filters with URL
  useEffect(() => {
    const newParams = new URLSearchParams(searchParams)
    if (tenantFilter) {
      newParams.set('tenant', tenantFilter)
    } else {
      newParams.delete('tenant')
    }
    if (domainFilter) {
      newParams.set('domain', domainFilter)
    } else {
      newParams.delete('domain')
    }
    setSearchParams(newParams, { replace: true })
  }, [tenantFilter, domainFilter, searchParams, setSearchParams])

  // Map config type to tab index
  const getTabIndex = (type: ConfigType): number => {
    switch (type) {
      case 'domain-packs':
        return 0
      case 'tenant-policies':
        return 1
      case 'playbooks':
        return 2
      case 'recommendations':
        return 3
      default:
        return 0
    }
  }

  // Map tab index to config type
  const getConfigTypeFromIndex = (index: number): ConfigType => {
    switch (index) {
      case 0:
        return 'domain-packs'
      case 1:
        return 'tenant-policies'
      case 2:
        return 'playbooks'
      case 3:
        return 'recommendations'
      default:
        return 'domain-packs'
    }
  }

  const [activeTab, setActiveTab] = useState(getTabIndex(configType))

  // Sync activeTab with URL when type param changes externally (e.g., browser back/forward)
  useEffect(() => {
    const currentTabIndex = getTabIndex(configType)
    if (currentTabIndex !== activeTab) {
      setActiveTab(currentTabIndex)
    }
  }, [configType, activeTab])

  // Handle tab change
  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue)
    const newType = getConfigTypeFromIndex(newValue)
    setConfigType(newType)
  }

  // Prepare filters for child components
  const filters: CommonConfigFilters = {
    tenantId: tenantFilter || undefined,
    domain: domainFilter || undefined,
  }

  // Handle item selection - navigate to detail page
  const handleSelectItem = (type: ConfigType, id: string) => {
    navigate(`/config/${type}/${encodeURIComponent(id)}`)
  }

  return (
    <PageShell>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {/* Header */}
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700, color: 'text.primary', mb: 0.5 }}>
            Config & Learning Console
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Browse domain packs, tenant policy packs, and playbooks
          </Typography>
        </Box>

        {/* Filters */}
        <Card>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={4}>
              <TextField
                fullWidth
                label="Tenant ID"
                value={tenantFilter}
                onChange={(e) => setTenantFilter(e.target.value)}
                placeholder="Filter by tenant ID"
                size="small"
                helperText="Leave empty to show all tenants"
              />
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <TextField
                fullWidth
                label="Domain"
                value={domainFilter}
                onChange={(e) => setDomainFilter(e.target.value)}
                placeholder="Filter by domain"
                size="small"
                helperText="Leave empty to show all domains"
              />
            </Grid>
          </Grid>
        </Card>

        {/* Config Type Tabs */}
        <Card noPadding>
          <Box sx={{ p: 2, pb: 0 }}>
            <Tabs value={activeTab} onChange={handleTabChange} aria-label="config type tabs">
              <Tab label="Domain Packs" id="config-tab-0" aria-controls="config-tabpanel-0" />
              <Tab label="Tenant Policy Packs" id="config-tab-1" aria-controls="config-tabpanel-1" />
              <Tab label="Playbooks" id="config-tab-2" aria-controls="config-tabpanel-2" />
              <Tab label="Recommendations" id="config-tab-3" aria-controls="config-tabpanel-3" />
            </Tabs>
          </Box>

          <Box sx={{ p: 2 }}>
            {/* Domain Packs Tab */}
            <TabPanel value={activeTab} index={0}>
              <DomainPacksList filters={filters} onSelectItem={handleSelectItem} />
            </TabPanel>

            {/* Tenant Policy Packs Tab */}
            <TabPanel value={activeTab} index={1}>
              <TenantPoliciesList filters={filters} onSelectItem={handleSelectItem} />
            </TabPanel>

            {/* Playbooks Tab */}
            <TabPanel value={activeTab} index={2}>
              <PlaybooksList filters={filters} onSelectItem={handleSelectItem} />
            </TabPanel>

            {/* Recommendations Tab */}
            <TabPanel value={activeTab} index={3}>
              <ConfigRecommendationsTab tenantId={filters.tenantId} domain={filters.domain} />
            </TabPanel>
          </Box>
        </Card>
      </Box>
    </PageShell>
  )
}
