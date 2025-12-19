import {
  Paper,
  Stack,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  useTheme,
  useMediaQuery,
} from '@mui/material'
import { useSearchParams } from 'react-router-dom'
import { useEffect } from 'react'

export interface OpsFilters {
  tenantId?: string
  domain?: string
  status?: string
  severity?: string
  eventType?: string
  dateFrom?: string
  dateTo?: string
  sourceSystem?: string
}

export interface OpsFilterBarProps {
  value: OpsFilters
  onChange: (filters: OpsFilters) => void
  showTenant?: boolean
  showDomain?: boolean
  showStatus?: boolean
  showSeverity?: boolean
  showEventType?: boolean
  showDateRange?: boolean
  showSourceSystem?: boolean
  syncWithUrl?: boolean
}

const SEVERITY_OPTIONS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
const STATUS_OPTIONS = ['pending', 'retrying', 'discarded', 'succeeded', 'fired', 'acknowledged', 'resolved']

/**
 * Enhanced FilterBar component for Ops pages
 * Supports URL synchronization and various filter types
 */
export default function OpsFilterBar({
  value,
  onChange,
  showTenant = false,
  showDomain = true,
  showStatus = true,
  showSeverity = false,
  showEventType = false,
  showDateRange = true,
  showSourceSystem = false,
  syncWithUrl = true,
}: OpsFilterBarProps) {
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const [searchParams, setSearchParams] = useSearchParams()

  // Sync URL params to filters on mount
  useEffect(() => {
    if (syncWithUrl) {
      const urlFilters: OpsFilters = {}
      if (searchParams.get('tenant_id')) urlFilters.tenantId = searchParams.get('tenant_id') || undefined
      if (searchParams.get('domain')) urlFilters.domain = searchParams.get('domain') || undefined
      if (searchParams.get('status')) urlFilters.status = searchParams.get('status') || undefined
      if (searchParams.get('severity')) urlFilters.severity = searchParams.get('severity') || undefined
      if (searchParams.get('event_type')) urlFilters.eventType = searchParams.get('event_type') || undefined
      if (searchParams.get('date_from')) urlFilters.dateFrom = searchParams.get('date_from') || undefined
      if (searchParams.get('date_to')) urlFilters.dateTo = searchParams.get('date_to') || undefined
      if (searchParams.get('source_system')) urlFilters.sourceSystem = searchParams.get('source_system') || undefined
      
      // Only update if there are URL params different from current value
      const hasChanges = Object.keys(urlFilters).some(key => urlFilters[key as keyof OpsFilters] !== value[key as keyof OpsFilters])
      if (hasChanges) {
        onChange({ ...value, ...urlFilters })
      }
    }
  }, []) // Only on mount

  const handleFilterChange = (key: keyof OpsFilters, newValue: string) => {
    const updatedFilters: OpsFilters = {
      ...value,
      [key]: newValue === '' ? undefined : newValue,
    }
    onChange(updatedFilters)

    // Sync to URL
    if (syncWithUrl) {
      const newParams = new URLSearchParams(searchParams)
      if (updatedFilters[key]) {
        newParams.set(key === 'tenantId' ? 'tenant_id' : key === 'eventType' ? 'event_type' : key === 'dateFrom' ? 'date_from' : key === 'dateTo' ? 'date_to' : key === 'sourceSystem' ? 'source_system' : key, updatedFilters[key]!)
      } else {
        newParams.delete(key === 'tenantId' ? 'tenant_id' : key === 'eventType' ? 'event_type' : key === 'dateFrom' ? 'date_from' : key === 'dateTo' ? 'date_to' : key === 'sourceSystem' ? 'source_system' : key)
      }
      setSearchParams(newParams, { replace: true })
    }
  }

  return (
    <Paper sx={{ p: 2, mb: 3 }}>
      <Stack
        direction={isMobile ? 'column' : 'row'}
        spacing={2}
        sx={{ flexWrap: 'wrap' }}
      >
        {showTenant && (
          <TextField
            size="small"
            label="Tenant ID"
            value={value.tenantId || ''}
            onChange={(e) => handleFilterChange('tenantId', e.target.value)}
            placeholder="Filter by tenant"
            sx={{ minWidth: { xs: '100%', sm: 150 } }}
          />
        )}

        {showDomain && (
          <TextField
            size="small"
            label="Domain"
            value={value.domain || ''}
            onChange={(e) => handleFilterChange('domain', e.target.value)}
            placeholder="Filter by domain"
            sx={{ minWidth: { xs: '100%', sm: 150 } }}
          />
        )}

        {showSeverity && (
          <FormControl size="small" sx={{ minWidth: { xs: '100%', sm: 150 } }}>
            <InputLabel>Severity</InputLabel>
            <Select
              value={value.severity || ''}
              label="Severity"
              onChange={(e) => handleFilterChange('severity', e.target.value)}
            >
              <MenuItem value="">
                <em>All</em>
              </MenuItem>
              {SEVERITY_OPTIONS.map((severity) => (
                <MenuItem key={severity} value={severity}>
                  {severity}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}

        {showStatus && (
          <FormControl size="small" sx={{ minWidth: { xs: '100%', sm: 150 } }}>
            <InputLabel>Status</InputLabel>
            <Select
              value={value.status || ''}
              label="Status"
              onChange={(e) => handleFilterChange('status', e.target.value)}
            >
              <MenuItem value="">
                <em>All</em>
              </MenuItem>
              {STATUS_OPTIONS.map((status) => (
                <MenuItem key={status} value={status}>
                  {status.charAt(0).toUpperCase() + status.slice(1)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}

        {showEventType && (
          <TextField
            size="small"
            label="Event Type"
            value={value.eventType || ''}
            onChange={(e) => handleFilterChange('eventType', e.target.value)}
            placeholder="Filter by event type"
            sx={{ minWidth: { xs: '100%', sm: 150 } }}
          />
        )}

        {showDateRange && (
          <>
            <TextField
              size="small"
              label="From"
              type="date"
              value={value.dateFrom || ''}
              onChange={(e) => handleFilterChange('dateFrom', e.target.value)}
              InputLabelProps={{
                shrink: true,
              }}
              sx={{ minWidth: { xs: '100%', sm: 150 } }}
            />
            <TextField
              size="small"
              label="To"
              type="date"
              value={value.dateTo || ''}
              onChange={(e) => handleFilterChange('dateTo', e.target.value)}
              InputLabelProps={{
                shrink: true,
              }}
              sx={{ minWidth: { xs: '100%', sm: 150 } }}
            />
          </>
        )}

        {showSourceSystem && (
          <TextField
            size="small"
            label="Source System"
            value={value.sourceSystem || ''}
            onChange={(e) => handleFilterChange('sourceSystem', e.target.value)}
            placeholder="Filter by source system"
            sx={{ minWidth: { xs: '100%', sm: 200 }, flexGrow: { sm: 1 } }}
          />
        )}
      </Stack>
    </Paper>
  )
}

