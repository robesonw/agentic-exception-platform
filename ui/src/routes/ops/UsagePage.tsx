import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Box, Grid, Card, CardContent, Typography, Button, FormControl, InputLabel, Select, MenuItem, CircularProgress, Alert } from '@mui/material'
import DownloadIcon from '@mui/icons-material/Download'
import { useTenant } from '../../hooks/useTenant'
import { getUsageSummary, getUsageDetails, exportUsage } from '../../api/ops'
import PageHeader from '../../components/common/PageHeader'
import DataTable from '../../components/common/DataTable'
import OpsFilterBar from '../../components/common/OpsFilterBar'
import { useSnackbar } from '../../components/common/SnackbarProvider'
import type { OpsFilters } from '../../components/common/OpsFilterBar'
import type { DataTableColumn } from '../../components/common/DataTable'
import type { UsageSummary } from '../../api/ops'

export default function UsagePage() {
  const { tenantId } = useTenant()
  const queryClient = useQueryClient()
  const { showSuccess, showError } = useSnackbar()
  const [period, setPeriod] = useState<'day' | 'week' | 'month'>('day')
  const [filters, setFilters] = useState<OpsFilters>({})
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)

  const { data: summaryData, isLoading: summaryLoading, dataUpdatedAt: summaryUpdatedAt } = useQuery({
    queryKey: ['usage-summary', tenantId, period],
    queryFn: () => getUsageSummary({ tenantId: tenantId || '', period }),
    enabled: !!tenantId,
    refetchInterval: 60000, // Refresh every minute
  })

  // Only fetch details when a metric type is explicitly selected AND date range is set
  // This prevents automatic queries on page load that could hit rate limits
  const shouldFetchDetails = !!filters.eventType && !!filters.dateFrom && !!filters.dateTo
  
  const metricType = filters.eventType || 'api_calls'
  const fromDate = filters.dateFrom
  const toDate = filters.dateTo

  const { data: detailsData, isLoading: detailsLoading, error: detailsError } = useQuery({
    queryKey: ['usage-details', tenantId, metricType, fromDate, toDate],
    queryFn: () => getUsageDetails({
      tenantId: tenantId || '',
      metricType: metricType,
      fromDate: fromDate!,
      toDate: toDate!,
    }),
    enabled: !!tenantId && shouldFetchDetails && !!fromDate && !!toDate,
    retry: false, // Don't retry on rate limit errors
    refetchOnWindowFocus: false, // Prevent refetch on window focus
    refetchOnMount: false, // Only fetch when explicitly enabled
  })

  const handleExport = async (format: 'csv' | 'json') => {
    if (!tenantId) return
    
    try {
      const blob = await exportUsage({ tenantId, period, format })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `usage-${period}-${new Date().toISOString()}.${format}`
      a.click()
      URL.revokeObjectURL(url)
      showSuccess(`Usage data exported as ${format.toUpperCase()}`)
    } catch (error) {
      showError(`Export failed: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['usage-summary', tenantId] })
    queryClient.invalidateQueries({ queryKey: ['usage-details', tenantId] })
  }

  const columns: DataTableColumn<{ resourceType: string; count: number; date: string }>[] = [
    {
      id: 'date',
      label: 'Date',
      accessor: (row) => new Date(row.date).toLocaleDateString(),
    },
    {
      id: 'resourceType',
      label: 'Resource Type',
      accessor: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
          {row.resourceType}
        </Typography>
      ),
    },
    {
      id: 'count',
      label: 'Count',
      numeric: true,
      accessor: (row) => row.count.toLocaleString(),
    },
  ]

  if (!tenantId) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">Please select a tenant to view usage data.</Alert>
      </Box>
    )
  }

  return (
    <Box>
      <PageHeader
        title="Usage Metering"
        subtitle="Track resource consumption by tenant and capability"
        lastUpdated={summaryUpdatedAt ? new Date(summaryUpdatedAt) : undefined}
        onRefresh={handleRefresh}
        actions={
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Period</InputLabel>
              <Select
                value={period}
                label="Period"
                onChange={(e) => setPeriod(e.target.value as 'day' | 'week' | 'month')}
              >
                <MenuItem value="day">Day</MenuItem>
                <MenuItem value="week">Week</MenuItem>
                <MenuItem value="month">Month</MenuItem>
              </Select>
            </FormControl>
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              onClick={() => handleExport('csv')}
              disabled={summaryLoading}
            >
              Export CSV
            </Button>
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              onClick={() => handleExport('json')}
              disabled={summaryLoading}
            >
              Export JSON
            </Button>
          </Box>
        }
      />

      {/* Summary Cards */}
      {summaryLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <Grid container spacing={3} sx={{ mb: 3 }}>
          {summaryData?.summary.map((item: UsageSummary) => (
            <Grid item xs={12} sm={6} md={3} key={item.resourceType}>
              <Card>
                <CardContent>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    {item.resourceType.replace(/_/g, ' ').toUpperCase()}
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700 }}>
                    {item.count.toLocaleString()}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {period} period
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Filters */}
      <OpsFilterBar
        value={filters}
        onChange={setFilters}
        showDateRange={true}
        showEventType={true}
        syncWithUrl={true}
      />
      
      {!shouldFetchDetails && (
        <Box sx={{ mt: 2 }}>
          <Alert severity="info">
            Select a metric type (e.g., api_calls, exceptions, tool_executions) and date range above to view detailed usage breakdown.
          </Alert>
        </Box>
      )}

      {/* Details Table - Only show when metric type is selected */}
      {shouldFetchDetails ? (
        <>
          {detailsError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {detailsError instanceof Error 
                ? detailsError.message 
                : 'Failed to load usage details. Please try again later.'}
            </Alert>
          )}
          <DataTable
            columns={columns}
            rows={detailsData?.items || []}
            loading={detailsLoading}
            page={page}
            pageSize={pageSize}
            totalCount={detailsData?.total || 0}
            onPageChange={setPage}
            onPageSizeChange={setPageSize}
            exportEnabled={true}
            emptyMessage="No usage data found for the selected period."
          />
        </>
      ) : (
        <Box sx={{ p: 3, textAlign: 'center' }}>
          <Alert severity="info">
            Select a metric type (e.g., api_calls, exceptions, tool_executions) and date range above to view detailed usage breakdown.
          </Alert>
        </Box>
      )}
    </Box>
  )
}

