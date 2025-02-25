# GitHub Device Flow Authentication Script
param(
    [string]$clientId = "mQNgcRlHzYqCLYF7"
)

try {
    # Step 1: Request device and user codes
    $response = Invoke-RestMethod -Uri "https://github.com/login/device/code" -Method Post -Body @{
        client_id = $clientId
        scope = "repo user workflow"
    } -Headers @{
        Accept = "application/json"
    }

    # Extract verification URI and user code
    $deviceCode = $response.device_code
    $userCode = $response.user_code
    $verificationUri = $response.verification_uri
    $interval = $response.interval

    # Display instructions to user
    Write-Host "`n=== GitHub Authentication ===`n" -ForegroundColor Cyan
    Write-Host "To sign in, use a web browser to open the page $verificationUri" -ForegroundColor Yellow
    Write-Host "and enter the code $userCode to authenticate.`n" -ForegroundColor Yellow
    
    # Open the browser automatically
    Start-Process $verificationUri

    # Step 2: Poll for completion
    Write-Host "Waiting for authentication..." -ForegroundColor Gray
    $token = $null
    $attempts = 0
    $maxAttempts = 60  # 5 minutes with 5-second interval

    while ($attempts -lt $maxAttempts) {
        try {
            $tokenResponse = Invoke-RestMethod -Uri "https://github.com/login/oauth/access_token" -Method Post -Body @{
                client_id = $clientId
                device_code = $deviceCode
                grant_type = "urn:ietf:params:oauth:grant-type:device_code"
            } -Headers @{
                Accept = "application/json"
            }

            if ($tokenResponse.access_token) {
                $token = $tokenResponse.access_token
                break
            }
        } catch {
            # Check if it's just a pending authorization
            if ($_.Exception.Response.StatusCode -ne 428) {
                throw
            }
        }

        Start-Sleep -Seconds $interval
        $attempts++
        
        # Show a progress indicator
        Write-Host "." -NoNewline -ForegroundColor Gray
    }

    if (-not $token) {
        throw "Authentication timed out. Please try again."
    }

    # Get user info to verify token
    $userInfo = Invoke-RestMethod -Uri "https://api.github.com/user" -Headers @{
        Authorization = "Bearer $token"
        Accept = "application/vnd.github.v3+json"
    }

    Write-Host "`n`nAuthentication successful!" -ForegroundColor Green
    Write-Host "Logged in as: $($userInfo.login)" -ForegroundColor Green

    # Save credentials to .env file
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