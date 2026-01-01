import {
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material'
import FilterRow, { filterInputSx } from './FilterRow'

export interface ExceptionFilters {
  domain?: string
  severity?: string
  status?: string
  dateFrom?: string
  dateTo?: string
  sourceSystem?: string
}

export interface FilterBarProps {
  value: ExceptionFilters
  onChange: (filters: ExceptionFilters) => void
}

const SEVERITY_OPTIONS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
const STATUS_OPTIONS = ['OPEN', 'IN_PROGRESS', 'RESOLVED', 'ESCALATED']

export default function FilterBar({ value, onChange }: FilterBarProps) {
  const handleFilterChange = (key: keyof ExceptionFilters, newValue: string) => {
    const updatedFilters: ExceptionFilters = {
      ...value,
      [key]: newValue === '' ? undefined : newValue,
    }
    onChange(updatedFilters)
  }

  return (
    <FilterRow>
      {/* Severity Filter */}
      <FormControl size="small" sx={{ minWidth: 120, ...filterInputSx }}>
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

      {/* Status Filter */}
      <FormControl size="small" sx={{ minWidth: 130, ...filterInputSx }}>
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
              {status.replace('_', ' ')}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {/* Date From Filter */}
      <TextField
        size="small"
        label="From"
        type="date"
        value={value.dateFrom || ''}
        onChange={(e) => handleFilterChange('dateFrom', e.target.value)}
        InputLabelProps={{ shrink: true }}
        sx={{ minWidth: 140, ...filterInputSx }}
      />

      {/* Date To Filter */}
      <TextField
        size="small"
        label="To"
        type="date"
        value={value.dateTo || ''}
        onChange={(e) => handleFilterChange('dateTo', e.target.value)}
        InputLabelProps={{ shrink: true }}
        sx={{ minWidth: 140, ...filterInputSx }}
      />

      {/* Domain Filter */}
      <TextField
        size="small"
        label="Domain"
        value={value.domain || ''}
        onChange={(e) => handleFilterChange('domain', e.target.value)}
        placeholder="Filter by domain"
        sx={{ minWidth: 130, ...filterInputSx }}
      />

      {/* Source System Filter */}
      <TextField
        size="small"
        label="Source"
        value={value.sourceSystem || ''}
        onChange={(e) => handleFilterChange('sourceSystem', e.target.value)}
        placeholder="Source system"
        sx={{ minWidth: 130, flexGrow: 1, ...filterInputSx }}
      />
    </FilterRow>
  )
}

