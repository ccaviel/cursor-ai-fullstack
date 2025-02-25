# GitHub Authentication Script using GitHub CLI
try {
    Write-Host "`nLogging in to GitHub..." -ForegroundColor Cyan
    
    # Check if already logged in
    $status = & "C:\Program Files\GitHub CLI\gh.exe" auth status 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`nAlready logged in to GitHub!" -ForegroundColor Green
        
        # Get the token
        $token = & "C:\Program Files\GitHub CLI\gh.exe" auth token
        
        # Save token to .env file
        $envPath = Join-Path $PSScriptRoot "../.env"
        if (Test-Path $envPath) {
            $envContent = Get-Content $envPath -Raw
            $envContent = $envContent -replace "GITHUB_ACCESS_TOKEN=.*", "GITHUB_ACCESS_TOKEN=$token"
            if ($envContent -notmatch "GITHUB_ACCESS_TOKEN=") {
                $envContent += "`nGITHUB_ACCESS_TOKEN=$token"
            }
            Set-Content $envPath $envContent
            Write-Host "`nToken has been saved to .env file" -ForegroundColor Green
        }
        
        # Show user info
        Write-Host "`nCurrent GitHub user:" -ForegroundColor Cyan
        & "C:\Program Files\GitHub CLI\gh.exe" api user | ConvertFrom-Json | Select-Object login,name,email | Format-List
        
        exit 0
    }

    # Login to GitHub
    Write-Host "`nStarting GitHub login process..." -ForegroundColor Yellow
    & "C:\Program Files\GitHub CLI\gh.exe" auth login --web --scopes "repo,workflow"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`nSuccessfully logged in to GitHub!" -ForegroundColor Green
        
        # Get the token
        $token = & "C:\Program Files\GitHub CLI\gh.exe" auth token
        
        # Save token to .env file
        $envPath = Join-Path $PSScriptRoot "../.env"
        if (Test-Path $envPath) {
            $envContent = Get-Content $envPath -Raw
            $envContent = $envContent -replace "GITHUB_ACCESS_TOKEN=.*", "GITHUB_ACCESS_TOKEN=$token"
            if ($envContent -notmatch "GITHUB_ACCESS_TOKEN=") {
                $envContent += "`nGITHUB_ACCESS_TOKEN=$token"
            }
            Set-Content $envPath $envContent
            Write-Host "`nToken has been saved to .env file" -ForegroundColor Green
        }
        
        # Show user info
        Write-Host "`nCurrent GitHub user:" -ForegroundColor Cyan
        & "C:\Program Files\GitHub CLI\gh.exe" api user | ConvertFrom-Json | Select-Object login,name,email | Format-List
    } else {
        throw "GitHub login failed"
    }
} catch {
    Write-Host "`nError: $_" -ForegroundColor Red
    exit 1
} 