import { Card, CardContent, Skeleton, Box } from '@mui/material'

export interface CardSkeletonProps {
  /**
   * Number of skeleton lines to display
   * @default 3
   */
  lines?: number
  /**
   * Optional title skeleton
   * @default true
   */
  showTitle?: boolean
}

/**
 * CardSkeleton component displays a loading skeleton for card content
 * Uses MUI Skeleton components to create a realistic card loading state
 */
export default function CardSkeleton({ lines = 3, showTitle = true }: CardSkeletonProps) {
  return (
    <Card>
      <CardContent>
        {showTitle && (
          <Box sx={{ mb: 2 }}>
            <Skeleton variant="text" width="60%" height={32} />
          </Box>
        )}
        {Array.from({ length: lines }).map((_, index) => (
          <Box key={`line-${index}`} sx={{ mb: index === lines - 1 ? 0 : 1 }}>
            <Skeleton
              variant="text"
              width={index === lines - 1 ? '40%' : '100%'}
              height={20}
            />
          </Box>
        ))}
      </CardContent>
    </Card>
  )
}

