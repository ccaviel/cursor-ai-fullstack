# Setup and test n8n workflow
param(
    [string]$n8nUrl = $env:N8N_CLOUD_URL
)

try {
    Write-Host "`nSetting up n8n workflow..." -ForegroundColor Cyan
    
    # First, ensure we have all required environment variables
    if (-not $n8nUrl) {
        throw "Missing required environment variables. Please ensure N8N_CLOUD_URL is set."
    }
    
    # Import the workflow using Python script
    Write-Host "`nImporting workflow to n8n..." -ForegroundColor Yellow
    python import_n8n_workflow.py
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to import workflow"
    }
    
    # Get the workflow ID from .env
    $envContent = Get-Content ../.env -Raw
    if ($envContent -match "N8N_WORKFLOW_ID=(.+)") {
        $workflowId = $matches[1]
        Write-Host "`nWorkflow ID: $workflowId" -ForegroundColor Green
    } else {
        throw "Could not find workflow ID in .env"
    }
    
    # Test the workflow with a sample request
    Write-Host "`nTesting workflow..." -ForegroundColor Yellow
    
    $headers = @{
        "Accept" = "application/json"
        "Content-Type" = "application/json"
    }
    
    $testPayload = @{
        title = "Test analysis request"
        description = "This is a test request to validate the RAG workflow setup."
    }
    
    # Test webhook endpoint
    $webhookUrl = "$n8nUrl/webhook/$workflowId/pr-review"
    Write-Host "Sending test webhook to: $webhookUrl"
    
    $response = Invoke-RestMethod -Uri $webhookUrl -Method Post -Headers $headers -Body ($testPayload | ConvertTo-Json)
    
    Write-Host "`nWorkflow test completed!" -ForegroundColor Green
    Write-Host "Response:" -ForegroundColor Cyan
    $response | ConvertTo-Json -Depth 5
    
} catch {
    Write-Host "`nError: $_" -ForegroundColor Red
    exit 1
} 