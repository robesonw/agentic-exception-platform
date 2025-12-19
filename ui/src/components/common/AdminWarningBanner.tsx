import { Alert, Typography } from '@mui/material'
import WarningIcon from '@mui/icons-material/Warning'

/**
 * AdminWarningBanner Component
 * 
 * Displays a warning banner on admin pages to remind users that
 * admin actions are audited and should be used with caution.
 */
export default function AdminWarningBanner() {
  return (
    <Alert 
      severity="warning" 
      icon={<WarningIcon />}
      sx={{ 
        mb: 3,
        '& .MuiAlert-message': {
          width: '100%',
        },
      }}
    >
      <Typography variant="body2" sx={{ fontWeight: 500 }}>
        <strong>Admin actions are audited.</strong> Use caution when making configuration changes.
      </Typography>
    </Alert>
  )
}

