# Test Exception Ingestion Script
# Tests the end-to-end flow: API ingestion -> Kafka -> Workers -> UI display

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Testing Exception Ingestion" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Test API key (from test files)
$apiKey = "test_api_key_tenant_001"
$tenantId = "TENANT_001"

# Test exception payload
$exceptionPayload = @{
    exception = @{
        sourceSystem = "ERP"
        rawPayload = @{
            error = "Test exception from PowerShell script"
            orderId = "ORD-TEST-001"
        }
    }
} | ConvertTo-Json -Depth 10

Write-Host "Ingesting test exception..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/exceptions/$tenantId" `
        -Method Post `
        -Headers @{"X-API-KEY" = $apiKey; "Content-Type" = "application/json"} `
        -Body $exceptionPayload
    
    Write-Host "[OK] Exception ingested successfully!" -ForegroundColor Green
    Write-Host "  Exception ID: $($response.exceptionId)" -ForegroundColor Cyan
    Write-Host "  Status: $($response.status)" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host "Waiting 5 seconds for workers to process..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    
    Write-Host ""
    Write-Host "Checking if exception appears in API..." -ForegroundColor Yellow
    try {
        $queryParams = "page=1&page_size=10"
        $uri = "http://localhost:8000/exceptions/$tenantId" + "?" + $queryParams
        $listResponse = Invoke-RestMethod -Uri $uri `
            -Method Get `
            -Headers @{"X-API-KEY" = $apiKey}
        
        Write-Host "[OK] Found $($listResponse.total) exception(s) in database" -ForegroundColor Green
        if ($listResponse.items.Count -gt 0) {
            Write-Host "  Latest exception: $($listResponse.items[0].exceptionId)" -ForegroundColor Cyan
        }
    } catch {
        $errMsg = $_.Exception.Message
        Write-Host "[FAIL] Failed to list exceptions: $errMsg" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "Test Summary" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "[OK] Exception ingestion: SUCCESS" -ForegroundColor Green
    Write-Host "  Exception ID: $($response.exceptionId)" -ForegroundColor White
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Check UI at http://localhost:3000" -ForegroundColor White
    Write-Host "  2. Login with tenant: $tenantId" -ForegroundColor White
    Write-Host "  3. View exceptions in Operations Center" -ForegroundColor White
    Write-Host ""
    
} catch {
    $errMsg = $_.Exception.Message
    Write-Host "[FAIL] Exception ingestion failed: $errMsg" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "  Response: $responseBody" -ForegroundColor Yellow
    }
    exit 1
}
