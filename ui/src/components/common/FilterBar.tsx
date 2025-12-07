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

export interface ExceptionFilters {
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
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))

  const handleFilterChange = (key: keyof ExceptionFilters, newValue: string) => {
    const updatedFilters: ExceptionFilters = {
      ...value,
      [key]: newValue === '' ? undefined : newValue,
    }
    onChange(updatedFilters)
  }

  return (
    <Paper sx={{ p: 2, mb: 3 }}>
      <Stack
        direction={isMobile ? 'column' : 'row'}
        spacing={2}
        sx={{ flexWrap: 'wrap' }}
      >
        {/* Severity Filter */}
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

        {/* Status Filter */}
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
          InputLabelProps={{
            shrink: true,
          }}
          sx={{ minWidth: { xs: '100%', sm: 150 } }}
        />

        {/* Date To Filter */}
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

        {/* Source System Filter */}
        <TextField
          size="small"
          label="Source System"
          value={value.sourceSystem || ''}
          onChange={(e) => handleFilterChange('sourceSystem', e.target.value)}
          placeholder="Filter by source system"
          sx={{ minWidth: { xs: '100%', sm: 200 }, flexGrow: { sm: 1 } }}
        />
      </Stack>
    </Paper>
  )
}

