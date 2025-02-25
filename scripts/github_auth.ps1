# GitHub OAuth Authentication Script
param(
    [string]$clientId = "mQNgcRlHzYqCLYF7",
    [string]$redirectUri = "http://localhost:8081/api/auth/github/callback"
)

try {
    # Generate state for security
    $state = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes([System.Guid]::NewGuid().ToString()))
    
    # Construct GitHub authorization URL
    $authUrl = "https://github.com/login/oauth/authorize?client_id=$clientId&redirect_uri=$redirectUri&state=$state&scope=repo,user,workflow"
    
    # Open browser for authentication
    Write-Host "`n=== GitHub Authentication ===`n" -ForegroundColor Cyan
    Write-Host "Opening browser for GitHub authentication..." -ForegroundColor Yellow
    Write-Host "Please authorize the application and copy the code from the callback URL." -ForegroundColor Yellow
    Start-Process $authUrl
    
    # Get the code from user input
    $code = Read-Host "`nEnter the code from the callback URL"
    
    # Exchange code for access token
    $tokenUrl = "https://github.com/login/oauth/access_token"
    $response = Invoke-RestMethod -Uri $tokenUrl -Method Post -Headers @{
        Accept = "application/json"
    } -Body @{
        client_id = $clientId
        code = $code
        redirect_uri = $redirectUri
    }
    
    if (-not $response.access_token) {
        throw "Failed to get access token. Please try again."
    }
    
    $token = $response.access_token
    
    # Test the token
    $userInfo = Invoke-RestMethod -Uri "https://api.github.com/user" -Headers @{
        Authorization = "Bearer $token"
        Accept = "application/vnd.github.v3+json"
    }
    
    Write-Host "`nAuthentication successful!" -ForegroundColor Green
    Write-Host "Logged in as: $($userInfo.login)" -ForegroundColor Green
    
    # Save token to .env file
    $envPath = Join-Path $PSScriptRoot "../.env"
    if (Test-Path $envPath) {
        $envContent = Get-Content $envPath -Raw
        $envContent = $envContent -replace "GITHUB_ACCESS_TOKEN=.*", "GITHUB_ACCESS_TOKEN=$token"
        if ($envContent -notmatch "GITHUB_ACCESS_TOKEN=") {
            $envContent += "`nGITHUB_ACCESS_TOKEN=$token"
        }
        Set-Content $envPath $envContent
        Write-Host "`nAccess token has been saved to .env file" -ForegroundColor Green
    }
    
    # Display token for verification
    Write-Host "`nAccess Token: $token" -ForegroundColor Yellow
    
} catch {
    Write-Host "`nError: $_" -ForegroundColor Red
    exit 1
} 