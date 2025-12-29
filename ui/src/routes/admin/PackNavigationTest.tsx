import React, { useEffect, useState } from 'react'
import { Box, Typography, Alert, List, ListItem, ListItemText, Button, Card, CardContent } from '@mui/material'
import { setApiKeyForHttpClient, setTenantIdForHttpClient } from '../../utils/httpClient'
import { listDomainPacks, listTenantPacks, getDomainPack, getTenantPack } from '../../api/onboarding'

/**
 * Test component for pack navigation and content viewing
 * This component tests the complete flow of authentication, API calls, and pack content display
 */
export default function PackNavigationTest() {
  const [testResults, setTestResults] = useState<Array<{
    test: string
    status: 'pending' | 'success' | 'error'
    message: string
    data?: any
  }>>([])

  const addTestResult = (test: string, status: 'success' | 'error', message: string, data?: any) => {
    setTestResults(prev => [...prev, { test, status, message, data }])
  }

  const runTests = async () => {
    setTestResults([])
    
    // Test 1: Authentication setup
    try {
      console.log('Setting up authentication...')
      setApiKeyForHttpClient('test-api-key-123')
      setTenantIdForHttpClient('tenant_001')
      addTestResult('Authentication Setup', 'success', 'API key and tenant ID configured')
    } catch (error) {
      addTestResult('Authentication Setup', 'error', `Failed: ${error}`)
      return
    }

    // Test 2: Domain packs listing
    try {
      console.log('Testing domain packs API...')
      const domainPacks = await listDomainPacks({ page: 1, page_size: 10 })
      addTestResult('Domain Packs API', 'success', `Found ${domainPacks.total} domain packs`, domainPacks)
    } catch (error) {
      addTestResult('Domain Packs API', 'error', `Failed: ${error}`)
    }

    // Test 3: Tenant packs listing
    try {
      console.log('Testing tenant packs API...')
      const tenantPacks = await listTenantPacks({ tenant_id: 'tenant_001', page: 1, page_size: 10 })
      addTestResult('Tenant Packs API', 'success', `Found ${tenantPacks.total} tenant packs`, tenantPacks)
    } catch (error) {
      addTestResult('Tenant Packs API', 'error', `Failed: ${error}`)
    }

    // Test 4: Domain pack detail
    try {
      console.log('Testing domain pack detail API...')
      // First get a domain pack from the list
      const domainPacks = await listDomainPacks({ page: 1, page_size: 1 })
      if (domainPacks.items.length > 0) {
        const pack = domainPacks.items[0]
        if (pack.domain && pack.version) {
          const packDetail = await getDomainPack(pack.domain, pack.version)
          addTestResult('Domain Pack Detail API', 'success', `Retrieved pack: ${pack.domain} v${pack.version}`, packDetail)
        } else {
          addTestResult('Domain Pack Detail API', 'error', 'No domain or version in pack')
        }
      } else {
        addTestResult('Domain Pack Detail API', 'error', 'No domain packs available for testing')
      }
    } catch (error) {
      addTestResult('Domain Pack Detail API', 'error', `Failed: ${error}`)
    }
  }

  useEffect(() => {
    // Run tests automatically when component mounts
    runTests()
  }, [])

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success': return '✅'
      case 'error': return '❌'
      case 'pending': return '⏳'
      default: return '❓'
    }
  }

  const getStatusColor = (status: string): "success" | "error" | "info" => {
    switch (status) {
      case 'success': return 'success'
      case 'error': return 'error'
      default: return 'info'
    }
  }

  return (
    <Box sx={{ p: 3, maxWidth: 1200 }}>
      <Typography variant="h4" gutterBottom>
        Pack Navigation Test Results
      </Typography>
      
      <Typography variant="body1" sx={{ mb: 3 }}>
        This page tests the complete pack navigation functionality including authentication, API calls, and data retrieval.
      </Typography>

      <Button variant="contained" onClick={runTests} sx={{ mb: 3 }}>
        Re-run Tests
      </Button>

      {testResults.length === 0 ? (
        <Alert severity="info">Running tests...</Alert>
      ) : (
        <List>
          {testResults.map((result, index) => (
            <ListItem key={index} sx={{ mb: 2 }}>
              <Card sx={{ width: '100%' }}>
                <CardContent>
                  <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <span style={{ marginRight: 8 }}>{getStatusIcon(result.status)}</span>
                    {result.test}
                  </Typography>
                  <Alert severity={getStatusColor(result.status)} sx={{ mb: result.data ? 2 : 0 }}>
                    {result.message}
                  </Alert>
                  {result.data && (
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="subtitle2" gutterBottom>
                        Response Data:
                      </Typography>
                      <pre style={{ 
                        backgroundColor: '#f5f5f5', 
                        padding: 12, 
                        borderRadius: 4, 
                        fontSize: '0.8rem',
                        overflow: 'auto',
                        maxHeight: 300
                      }}>
                        {JSON.stringify(result.data, null, 2)}
                      </pre>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </ListItem>
          ))}
        </List>
      )}

      <Box sx={{ mt: 4 }}>
        <Typography variant="h5" gutterBottom>
          Next Steps:
        </Typography>
        <Typography variant="body1">
          1. If all tests pass, navigate to Admin → Packs to see the pack management interface
          <br />
          2. Try viewing pack details by clicking on a pack in the table
          <br />
          3. Check the Pack Content Viewer tabs (Overview, Raw JSON, Playbooks, Tools, Policies)
          <br />
          4. Test the workflow diagram functionality for playbooks
        </Typography>
      </Box>
    </Box>
  )
}