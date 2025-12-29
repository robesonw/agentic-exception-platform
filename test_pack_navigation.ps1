#!/usr/bin/env pwsh
# Test authentication and navigation to admin packs

Write-Host "Testing authentication and pack navigation..." -ForegroundColor Green

# Test the login endpoint to get session information
try {
    # First, check if the API is responding
    $healthResponse = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method GET -TimeoutSec 10
    Write-Host "API Health Check: $($healthResponse.status)" -ForegroundColor Green
} catch {
    Write-Host "❌ Backend API is not responding on localhost:8000" -ForegroundColor Red
    Write-Host "Please make sure the backend is running with: .\scripts\start-all.ps1" -ForegroundColor Yellow
    exit 1
}

# Test domain packs endpoint with authentication
$apiKey = "test-api-key-123"
$headers = @{
    'X-API-KEY' = $apiKey
    'Content-Type' = 'application/json'
}

try {
    Write-Host "Testing domain packs API with authentication..." -ForegroundColor Yellow
    $packResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/onboarding/domain-packs" -Method GET -Headers $headers -TimeoutSec 10
    Write-Host "✅ Domain packs API responding successfully" -ForegroundColor Green
    Write-Host "Found $($packResponse.total) total domain packs" -ForegroundColor Cyan
    if ($packResponse.items) {
        Write-Host "Sample pack: $($packResponse.items[0].domain) v$($packResponse.items[0].version)" -ForegroundColor Cyan
    }
} catch {
    Write-Host "❌ Domain packs API failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Response: $($_.ErrorDetails)" -ForegroundColor Yellow
}

# Test tenant packs endpoint
try {
    Write-Host "Testing tenant packs API with authentication..." -ForegroundColor Yellow
    $tenantPackResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/onboarding/tenant-packs?tenant_id=tenant_001" -Method GET -Headers $headers -TimeoutSec 10
    Write-Host "✅ Tenant packs API responding successfully" -ForegroundColor Green
    Write-Host "Found $($tenantPackResponse.total) total tenant packs" -ForegroundColor Cyan
} catch {
    Write-Host "❌ Tenant packs API failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Response: $($_.ErrorDetails)" -ForegroundColor Yellow
}

# Check if UI dev server is running
try {
    $uiResponse = Invoke-WebRequest -Uri "http://localhost:3000" -Method GET -TimeoutSec 5 -UseBasicParsing
    if ($uiResponse.StatusCode -eq 200) {
        Write-Host "✅ UI Dev Server responding on localhost:3000" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ UI Dev Server is not responding on localhost:3000" -ForegroundColor Red
    Write-Host "Please make sure the UI is running with: cd ui && npm run dev" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🌐 To test the UI navigation:" -ForegroundColor Cyan
Write-Host "1. Open browser to: http://localhost:3000" -ForegroundColor White
Write-Host "2. Login with API Key: test-api-key-123" -ForegroundColor White
Write-Host "3. Select Tenant: tenant_001" -ForegroundColor White
Write-Host "4. Select Domain: TestDomain" -ForegroundColor White
Write-Host "5. Navigate to: Admin → Packs → Domain Packs" -ForegroundColor White
Write-Host "6. Try viewing pack details and content" -ForegroundColor White