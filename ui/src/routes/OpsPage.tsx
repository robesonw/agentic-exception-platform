/**
 * Operations Page
 * 
 * Displays Dead Letter Queue entries for monitoring and debugging.
 * Hidden behind VITE_ENABLE_OPS_PAGE environment flag.
 */

import { useQuery } from '@tanstack/react-query'
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Alert,
  Pagination,
  CircularProgress,
  Stack,
} from '@mui/material'
import ErrorIcon from '@mui/icons-material/Error'
import { listDLQEntries } from '../api/ops'
import { useTenant } from '../hooks/useTenant'
import { formatDateTime } from '../utils/dateFormat'
import { useState } from 'react'

const ITEMS_PER_PAGE = 50

export default function OpsPage() {
  const { tenantId } = useTenant()
  const [page, setPage] = useState(1)
  const offset = (page - 1) * ITEMS_PER_PAGE

  // Check if Ops page is enabled via environment variable
  const isOpsPageEnabled = import.meta.env.VITE_ENABLE_OPS_PAGE === 'true'

  if (!isOpsPageEnabled) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">
          Operations page is not enabled. Set VITE_ENABLE_OPS_PAGE=true to enable.
        </Alert>
      </Box>
    )
  }

  // Fetch DLQ entries
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['dlq-entries', tenantId, page],
    queryFn: () => {
      if (!tenantId) {
        throw new Error('Tenant ID is required')
      }
      return listDLQEntries({
        tenantId,
        limit: ITEMS_PER_PAGE,
        offset,
      })
    },
    enabled: !!tenantId && isOpsPageEnabled,
    refetchInterval: 10000, // Refresh every 10 seconds
  })

  const handlePageChange = (_event: React.ChangeEvent<unknown>, value: number) => {
    setPage(value)
  }

  const totalPages = data ? Math.ceil(data.total / ITEMS_PER_PAGE) : 1

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          Operations - Dead Letter Queue
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Monitor events that failed processing after maximum retries
        </Typography>
      </Box>

      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load DLQ entries: {error instanceof Error ? error.message : 'Unknown error'}
        </Alert>
      )}

      {data && (
        <>
          <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="body2" color="text.secondary">
              Total entries: {data.total}
            </Typography>
            {data.total > 0 && (
              <Chip
                icon={<ErrorIcon />}
                label={`${data.total} failed events`}
                color="error"
                size="small"
              />
            )}
          </Box>

          {data.items.length === 0 ? (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography variant="body1" color="text.secondary">
                No DLQ entries found
              </Typography>
            </Paper>
          ) : (
            <>
              <TableContainer component={Paper}>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Event ID</TableCell>
                      <TableCell>Event Type</TableCell>
                      <TableCell>Exception ID</TableCell>
                      <TableCell>Worker Type</TableCell>
                      <TableCell>Failure Reason</TableCell>
                      <TableCell>Retry Count</TableCell>
                      <TableCell>Failed At</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.items.map((entry) => (
                      <TableRow key={entry.eventId} hover>
                        <TableCell>
                          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                            {entry.eventId.substring(0, 8)}...
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip label={entry.eventType} size="small" variant="outlined" />
                        </TableCell>
                        <TableCell>
                          {entry.exceptionId ? (
                            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                              {entry.exceptionId.substring(0, 8)}...
                            </Typography>
                          ) : (
                            <Typography variant="body2" color="text.secondary">
                              —
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell>
                          <Chip label={entry.workerType} size="small" color="secondary" />
                        </TableCell>
                        <TableCell>
                          <Typography
                            variant="body2"
                            sx={{
                              maxWidth: 300,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                            title={entry.failureReason}
                          >
                            {entry.failureReason}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={entry.retryCount}
                            size="small"
                            color={entry.retryCount > 3 ? 'error' : 'warning'}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" sx={{ fontSize: '0.875rem' }}>
                            {formatDateTime(entry.failedAt)}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>

              {totalPages > 1 && (
                <Stack spacing={2} sx={{ mt: 3, alignItems: 'center' }}>
                  <Pagination
                    count={totalPages}
                    page={page}
                    onChange={handlePageChange}
                    color="primary"
                    showFirstButton
                    showLastButton
                  />
                </Stack>
              )}
            </>
          )}
        </>
      )}
    </Box>
  )
}

