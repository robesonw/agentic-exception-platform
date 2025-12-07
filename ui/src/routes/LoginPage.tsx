import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Typography,
  Box,
  Paper,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Stack,
  TextField,
} from '@mui/material'
import { useTenant } from '../hooks/useTenant.tsx'
import { useDocumentTitle } from '../hooks/useDocumentTitle.ts'
import { setApiKeyForHttpClient, setTenantIdForHttpClient } from '../utils/httpClient.ts'

// Sample tenant/domain options for demo (can be replaced with API call later)
const SAMPLE_TENANTS = ['tenant_001', 'TENANT_001', 'TENANT_002', 'TENANT_FINANCE_001']
const SAMPLE_DOMAINS = ['TestDomain', 'Finance', 'Healthcare', 'Retail']

// Sample API keys for demo (matching backend test keys)
// In production, these would come from a secure auth service
const SAMPLE_API_KEYS = [
  { key: 'test-api-key-123', tenant: 'tenant_001', label: 'tenant_001 (Admin)' },
  { key: 'test_api_key_tenant_001', tenant: 'TENANT_001', label: 'TENANT_001 (Admin)' },
  { key: 'test_api_key_tenant_002', tenant: 'TENANT_002', label: 'TENANT_002 (Operator)' },
  { key: 'test_api_key_tenant_finance', tenant: 'TENANT_FINANCE_001', label: 'TENANT_FINANCE_001 (Admin)' },
]

export default function LoginPage() {
  useDocumentTitle('Login')
  const navigate = useNavigate()
  const { tenantId, domain, apiKey, setTenantId, setDomain, setApiKey } = useTenant()
  const [selectedTenant, setSelectedTenant] = useState<string>(tenantId || '')
  const [selectedDomain, setSelectedDomain] = useState<string>(domain || '')
  const [selectedApiKey, setSelectedApiKey] = useState<string>(apiKey || '')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (selectedTenant && selectedDomain && selectedApiKey) {
      // Set API key and tenant ID synchronously in httpClient BEFORE navigation
      // This ensures they're available immediately when the next page makes API calls
      setApiKeyForHttpClient(selectedApiKey)
      setTenantIdForHttpClient(selectedTenant)
      
      // Also update React state (which will persist to localStorage via useEffect)
      setTenantId(selectedTenant)
      setDomain(selectedDomain)
      setApiKey(selectedApiKey)
      
      // Small delay to ensure state is set before navigation
      // This prevents race conditions where API calls happen before state is ready
      setTimeout(() => {
        navigate('/exceptions')
      }, 0)
    }
  }

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        backgroundColor: 'background.default',
      }}
    >
      <Paper sx={{ p: 4, maxWidth: 400, width: '100%' }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Login
        </Typography>
        <Typography variant="body1" color="text.secondary" paragraph>
          Tenant, Domain, and API Key Selection
        </Typography>
        <form onSubmit={handleSubmit}>
          <Stack spacing={3}>
            <FormControl fullWidth required>
              <InputLabel>API Key</InputLabel>
              <Select
                value={selectedApiKey}
                onChange={(e) => {
                  const key = e.target.value
                  setSelectedApiKey(key)
                  // Auto-select tenant based on API key
                  const apiKeyInfo = SAMPLE_API_KEYS.find((ak) => ak.key === key)
                  if (apiKeyInfo) {
                    setSelectedTenant(apiKeyInfo.tenant)
                  }
                }}
                label="API Key"
              >
                {SAMPLE_API_KEYS.map((ak) => (
                  <MenuItem key={ak.key} value={ak.key}>
                    {ak.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl fullWidth required>
              <InputLabel>Tenant</InputLabel>
              <Select
                value={selectedTenant}
                onChange={(e) => setSelectedTenant(e.target.value)}
                label="Tenant"
              >
                {SAMPLE_TENANTS.map((tenant) => (
                  <MenuItem key={tenant} value={tenant}>
                    {tenant}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl fullWidth required>
              <InputLabel>Domain</InputLabel>
              <Select
                value={selectedDomain}
                onChange={(e) => setSelectedDomain(e.target.value)}
                label="Domain"
              >
                {SAMPLE_DOMAINS.map((dom) => (
                  <MenuItem key={dom} value={dom}>
                    {dom}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <TextField
              fullWidth
              label="API Key (manual entry)"
              type="password"
              value={selectedApiKey}
              onChange={(e) => setSelectedApiKey(e.target.value)}
              helperText="Select from dropdown above or enter manually. Test keys: test-api-key-123, test_api_key_tenant_001, etc."
              required
            />

            <Button
              type="submit"
              variant="contained"
              fullWidth
              disabled={!selectedTenant || !selectedDomain || !selectedApiKey}
              size="large"
            >
              Continue
            </Button>
          </Stack>
        </form>
        {tenantId && domain && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Current: {tenantId} / {domain}
          </Typography>
        )}
      </Paper>
    </Box>
  )
}
