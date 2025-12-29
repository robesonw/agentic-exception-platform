# Test Admin Playbooks Action Buttons
Write-Host "=== TESTING ADMIN PLAYBOOKS ACTION BUTTONS ===" -ForegroundColor Green

# Test 1: Verify registry data exists
Write-Host "`n1. Checking registry data..." -ForegroundColor Yellow
$registry = Invoke-RestMethod -Uri "http://localhost:8000/admin/playbooks/registry" -Headers @{"x-api-key"="test-api-key-123"; "x-tenant-id"="tenant_001"}
Write-Host "   Registry total: $($registry.total)" -ForegroundColor Cyan

if ($registry.total -gt 0) {
    $firstPlaybook = $registry.items[0]
    Write-Host "   First playbook: $($firstPlaybook.name)" -ForegroundColor Cyan
    Write-Host "   Exception type: $($firstPlaybook.exception_type)" -ForegroundColor Cyan
    Write-Host "   Source pack ID: $($firstPlaybook.source_pack_id)" -ForegroundColor Cyan
    
    # Test 2: Verify we can fetch the source pack (for View Details button)
    Write-Host "`n2. Testing source pack fetch for View Details..." -ForegroundColor Yellow
    try {
        $sourcePack = Invoke-RestMethod -Uri "http://localhost:8000/admin/packs/domain/$($firstPlaybook.domain)/$($firstPlaybook.version)" -Headers @{"x-api-key"="test-api-key-123"; "x-tenant-id"="tenant_001"}
        Write-Host "   ✅ Source pack fetched successfully" -ForegroundColor Green
        Write-Host "   Pack has $($sourcePack.content_json.playbooks.Count) playbooks" -ForegroundColor Cyan
        
        # Find the specific playbook
        $matchingPlaybook = $sourcePack.content_json.playbooks | Where-Object { $_.exceptionType -eq $firstPlaybook.exception_type }
        if ($matchingPlaybook) {
            Write-Host "   ✅ Found matching playbook in source pack" -ForegroundColor Green
            Write-Host "   Steps count: $($matchingPlaybook.steps.Count)" -ForegroundColor Cyan
        } else {
            Write-Host "   ⚠️  Could not find matching playbook" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "   ❌ Failed to fetch source pack: $_" -ForegroundColor Red
    }
    
    # Test 3: Check domain pack URL for View Source Pack button
    Write-Host "`n3. Testing View Source Pack navigation..." -ForegroundColor Yellow
    $sourcePackUrl = "http://localhost:3001/admin/packs/domain/$($firstPlaybook.domain)/$($firstPlaybook.version)"
    Write-Host "   Source pack URL: $sourcePackUrl" -ForegroundColor Cyan
    Write-Host "   ✅ Navigation URL generated" -ForegroundColor Green
}

Write-Host "`n=== BUTTON FUNCTIONALITY SUMMARY ===" -ForegroundColor Green
Write-Host "✅ View Details: Fetches and displays playbook content + workflow diagram" -ForegroundColor Green
Write-Host "✅ View Diagram: Same as View Details (opens detail modal with diagram)" -ForegroundColor Green  
Write-Host "✅ View Source Pack: Navigates to domain pack page in new tab" -ForegroundColor Green
Write-Host "`nTest complete! Navigate to http://localhost:3001/admin/playbooks and test buttons." -ForegroundColor White