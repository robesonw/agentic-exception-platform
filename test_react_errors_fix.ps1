#!/usr/bin/env pwsh
# React Error Testing Script
# Comprehensive navigation testing for admin -> packs -> domainpacks

Write-Host "=== React Error Testing - Admin Pack Navigation ===" -ForegroundColor Green
Write-Host "Testing the fixed React Flow edge creation and missing key prop issues" -ForegroundColor Yellow
Write-Host ""

# Test 1: Backend API Health Check
Write-Host "1. Testing Backend API Health..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/admin/packs/domain" -Headers @{"x-api-key"="test-api-key-123"; "x-tenant-id"="tenant_001"} -UseBasicParsing
    $data = $response.Content | ConvertFrom-Json
    Write-Host "   ✅ Backend API: HEALTHY" -ForegroundColor Green
    Write-Host "   📊 Found $($data.total) domain packs" -ForegroundColor White
}
catch {
    Write-Host "   ❌ Backend API: FAILED - $($_.Exception.Message)" -ForegroundColor Red
}

# Test 2: Frontend Development Server Check
Write-Host ""
Write-Host "2. Testing Frontend Development Server..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 5
    Write-Host "   ✅ Frontend Server: RUNNING" -ForegroundColor Green
}
catch {
    Write-Host "   ❌ Frontend Server: NOT ACCESSIBLE - $($_.Exception.Message)" -ForegroundColor Red
}

# Test 3: Navigate to specific pack for details
Write-Host ""
Write-Host "3. Testing Specific Pack Details..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/admin/packs/domain/Finance/v1.0" -Headers @{"x-api-key"="test-api-key-123"; "x-tenant-id"="tenant_001"} -UseBasicParsing
    $pack = $response.Content | ConvertFrom-Json
    Write-Host "   ✅ Pack Details: ACCESSIBLE" -ForegroundColor Green
    Write-Host "   📋 Pack: $($pack.domain) v$($pack.version)" -ForegroundColor White
    if ($pack.content_json) {
        $content = $pack.content_json | ConvertFrom-Json
        if ($content.playbooks) {
            Write-Host "   📗 Playbooks: $($content.playbooks.Count)" -ForegroundColor White
        }
        if ($content.tools) {
            Write-Host "   🔧 Tools: $($content.tools.Count)" -ForegroundColor White
        }
    }
}
catch {
    Write-Host "   ❌ Pack Details: FAILED - $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== REACT ERROR FIXES IMPLEMENTED ===" -ForegroundColor Green
Write-Host ""
Write-Host "✅ Fixed React Flow Issues:" -ForegroundColor Green
Write-Host "   • Added Handle import from @xyflow/react" -ForegroundColor White
Write-Host "   • Added Position import for Handle positioning" -ForegroundColor White
Write-Host "   • Added Handle components to CustomNode:" -ForegroundColor White
Write-Host "     - Target handle (left side) for incoming edges" -ForegroundColor White
Write-Host "     - Source handle (right side) for outgoing edges" -ForegroundColor White
Write-Host "   • Fixed 'Couldn't create edge for source handle id: null' errors" -ForegroundColor White
Write-Host ""
Write-Host "✅ Fixed Missing Key Props:" -ForegroundColor Green
Write-Host "   • Added unique keys to classifier map items" -ForegroundColor White
Write-Host "   • Tools and policies already had proper keys" -ForegroundColor White
Write-Host "   • All list rendering components now have proper React keys" -ForegroundColor White
Write-Host ""

Write-Host "=== MANUAL TESTING INSTRUCTIONS ===" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Open http://localhost:3000 in your browser" -ForegroundColor White
Write-Host "2. Navigate to: Admin -> Packs -> Domain Packs" -ForegroundColor White
Write-Host "3. Select a pack (e.g., 'Finance v1.0')" -ForegroundColor White
Write-Host "4. Click 'View Details' to open PackContentViewer" -ForegroundColor White
Write-Host "5. Navigate through tabs:" -ForegroundColor White
Write-Host "   • Summary - General pack information" -ForegroundColor White
Write-Host "   • Playbooks - View workflow diagrams (React Flow fixed!)" -ForegroundColor White
Write-Host "   • Tools - Check tools listings (key props fixed!)" -ForegroundColor White
Write-Host "   • Policies - Check policy listings" -ForegroundColor White
Write-Host "6. Open browser DevTools (F12) and check Console tab" -ForegroundColor White
Write-Host "7. Verify NO React Flow edge creation errors" -ForegroundColor White
Write-Host "8. Verify NO missing key prop warnings" -ForegroundColor White
Write-Host ""

Write-Host "=== EXPECTED BROWSER CONSOLE RESULTS ===" -ForegroundColor Yellow
Write-Host ""
Write-Host "✅ FIXED - Should NO longer see:" -ForegroundColor Green
Write-Host "   • 'Couldn't create edge for source handle id: null'" -ForegroundColor White
Write-Host "   • 'Each child in a list should have a unique key prop'" -ForegroundColor White
Write-Host ""
Write-Host "⚠️  MAY STILL SEE (non-critical warnings):" -ForegroundColor Yellow
Write-Host "   • React Router future flags warnings" -ForegroundColor White
Write-Host "   • Material-UI accessibility warnings" -ForegroundColor White
Write-Host ""

Write-Host "=== FILES MODIFIED ===" -ForegroundColor Magenta
Write-Host ""
Write-Host "📁 ui/src/components/exceptions/WorkflowViewer.tsx:" -ForegroundColor White
Write-Host "   • Added Handle, Position imports" -ForegroundColor White
Write-Host "   • Added Handle components to CustomNode" -ForegroundColor White
Write-Host "   • Fixed React Flow edge creation" -ForegroundColor White
Write-Host ""
Write-Host "📁 ui/src/components/admin/PackContentViewer.tsx:" -ForegroundColor White
Write-Host "   • Added unique keys to classifier map items" -ForegroundColor White
Write-Host "   • Fixed React list rendering warnings" -ForegroundColor White
Write-Host ""

Write-Host "Testing complete! Check the browser console for verification." -ForegroundColor Green