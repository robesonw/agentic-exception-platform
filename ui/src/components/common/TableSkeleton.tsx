import { TableBody, TableCell, TableRow, Skeleton } from '@mui/material'

export interface TableSkeletonProps {
  /**
   * Number of skeleton rows to display
   * @default 5
   */
  rowCount?: number
  /**
   * Number of skeleton columns to display
   * @default 5
   */
  columnCount?: number
}

/**
 * TableSkeleton component displays skeleton rows for table loading state
 * Renders TableBody with skeleton rows that can be inserted into an existing Table structure
 * Uses MUI Skeleton components to create a realistic loading state
 */
export default function TableSkeleton({ rowCount = 5, columnCount = 5 }: TableSkeletonProps) {
  return (
    <TableBody>
      {Array.from({ length: rowCount }).map((_, rowIndex) => (
        <TableRow key={`skeleton-row-${rowIndex}`}>
          {Array.from({ length: columnCount }).map((_, colIndex) => (
            <TableCell key={`skeleton-cell-${rowIndex}-${colIndex}`}>
              <Skeleton variant="text" width={colIndex === 0 ? '80%' : '60%'} />
            </TableCell>
          ))}
        </TableRow>
      ))}
    </TableBody>
  )
}

