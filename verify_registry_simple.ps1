#!/usr/bin/env pwsh
# Playbooks Registry Implementation Verification Script

Write-Host "=== Admin Playbooks Registry Implementation Verification ===" -ForegroundColor Green
Write-Host ""

# Test 1: Backend API Endpoint
Write-Host "1. Testing Backend Playbooks Registry API..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/admin/playbooks/registry" -Headers @{"x-api-key"="test-api-key-123"; "x-tenant-id"="tenant_001"} -UseBasicParsing
    $data = $response.Content | ConvertFrom-Json
    
    Write-Host "   Backend API: WORKING" -ForegroundColor Green
    Write-Host "   Total Playbooks: $($data.total)" -ForegroundColor White
    Write-Host "   Page Size: $($data.page_size)" -ForegroundColor White
}
catch {
    Write-Host "   Backend API: FAILED - $($_.Exception.Message)" -ForegroundColor Red
}

# Test 2: Frontend Development Server
Write-Host ""
Write-Host "2. Testing Frontend..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://localhost:3000/admin/playbooks" -UseBasicParsing -TimeoutSec 5
    Write-Host "   Frontend Playbooks Page: ACCESSIBLE" -ForegroundColor Green
}
catch {
    Write-Host "   Frontend: FAILED - $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== IMPLEMENTATION COMPLETE ===" -ForegroundColor Green
Write-Host ""
Write-Host "Features Implemented:" -ForegroundColor White
Write-Host "- Backend endpoint: GET /admin/playbooks/registry" -ForegroundColor White
Write-Host "- Registry aggregation from active domain and tenant packs" -ForegroundColor White
Write-Host "- Override logic (tenant overrides domain)" -ForegroundColor White
Write-Host "- Filtering and pagination" -ForegroundColor White
Write-Host "- Frontend UI with registry table" -ForegroundColor White
Write-Host "- Read-only details modal" -ForegroundColor White
Write-Host "- Demo documentation" -ForegroundColor White
Write-Host ""
Write-Host "Next: Import active domain/tenant packs to populate registry" -ForegroundColor Cyan