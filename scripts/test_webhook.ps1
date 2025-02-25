# Test n8n Webhook Script
param(
    [string]$webhookUrl = $env:N8N_WEBHOOK_URL,
    [string]$webhookId = $env:N8N_WEBHOOK_ID
)

try {
    # Get GitHub token
    $githubToken = gh auth token

    if (-not $githubToken) {
        throw "Not authenticated with GitHub. Please run 'gh auth login' first."
    }

    # Prepare test payload
    $payload = @{
        event = "test"
        action = "webhook_test"
        timestamp = Get-Date -Format "o"
        github_token = $githubToken
    }

    # Prepare headers
    $headers = @{
        "Accept" = "application/json"
        "Content-Type" = "application/json"
        "X-N8N-Webhook-ID" = $webhookId
    }

    Write-Host "`nSending test webhook to n8n..." -ForegroundColor Cyan
    
    # Send webhook
    $response = Invoke-RestMethod -Uri $webhookUrl -Method Post -Body ($payload | ConvertTo-Json) -Headers $headers

    Write-Host "`nWebhook test successful!" -ForegroundColor Green
    Write-Host "Response:" -ForegroundColor Cyan
    $response | ConvertTo-Json -Depth 10

} catch {
    Write-Host "`nError testing webhook: $_" -ForegroundColor Red
    exit 1
} 