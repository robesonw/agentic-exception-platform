$headers = @{
    'x-api-key' = 'test_api_key_tenant_001'
    'Content-Type' = 'application/json'
}

$body = @{
    message = "provide summary domain exceptions"
    tenant_id = "TENANT_001"
    domain = "finance"
} | ConvertTo-Json

try {
    $response = Invoke-WebRequest -Uri 'http://localhost:8000/api/copilot/chat' -Method POST -Headers $headers -Body $body -UseBasicParsing
    Write-Host "Status: $($response.StatusCode)"
    Write-Host "Content: $($response.Content)"
} catch {
    Write-Host "Error: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseText = $reader.ReadToEnd()
        Write-Host "Response: $responseText"
    }
}