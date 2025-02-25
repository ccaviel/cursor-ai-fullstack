# Azure AD Authentication Script
try {
    Write-Host "`n=== Microsoft Entra ID Authentication ===" -ForegroundColor Cyan
    
    # Install required modules if not present
    if (-not (Get-Module -ListAvailable -Name Az.Accounts)) {
        Write-Host "`nInstalling Az PowerShell module..." -ForegroundColor Yellow
        Install-Module -Name Az.Accounts -Scope CurrentUser -Force
        Write-Host "Az module installed successfully!" -ForegroundColor Green
    }

    # Connect to Azure
    Write-Host "`nOpening Azure login window..." -ForegroundColor Yellow
    Connect-AzAccount

    # Get current context
    $context = Get-AzContext
    $tenantId = $context.Tenant.Id
    $subscriptionId = $context.Subscription.Id

    Write-Host "`nConnected to Azure!" -ForegroundColor Green
    Write-Host "Tenant ID: $tenantId" -ForegroundColor Cyan
    Write-Host "Subscription ID: $subscriptionId" -ForegroundColor Cyan

    # Create new app registration
    $appName = "Cursor-AI-Integration-$(Get-Random)"
    Write-Host "`nCreating new app registration '$appName'..." -ForegroundColor Yellow

    # Get access token for Microsoft Graph
    $token = Get-AzAccessToken -ResourceUrl "https://graph.microsoft.com"
    
    # Create app registration using Microsoft Graph API
    $headers = @{
        'Authorization' = "Bearer $($token.Token)"
        'Content-Type' = 'application/json'
    }

    $body = @{
        'displayName' = $appName
        'signInAudience' = 'AzureADMyOrg'
        'api' = @{
            'requestedAccessTokenVersion' = 2
        }
    } | ConvertTo-Json

    $response = Invoke-RestMethod -Method Post `
        -Uri "https://graph.microsoft.com/v1.0/applications" `
        -Headers $headers `
        -Body $body

    $clientId = $response.appId
    Write-Host "App registration created successfully!" -ForegroundColor Green
    Write-Host "Client ID: $clientId" -ForegroundColor Cyan

    # Create client secret
    $secretBody = @{
        'passwordCredential' = @{
            'displayName' = 'Cursor AI Integration Secret'
            'endDateTime' = (Get-Date).AddYears(1).ToString('yyyy-MM-dd')
        }
    } | ConvertTo-Json

    $secretResponse = Invoke-RestMethod -Method Post `
        -Uri "https://graph.microsoft.com/v1.0/applications/$($response.id)/addPassword" `
        -Headers $headers `
        -Body $secretBody

    $clientSecret = $secretResponse.secretText
    Write-Host "Client secret created successfully!" -ForegroundColor Green

    # Save configuration to .env file
    $envPath = Join-Path $PSScriptRoot "../.env"
    if (Test-Path $envPath) {
        $envContent = Get-Content $envPath -Raw
        
        # Update Azure configuration
        $envUpdates = @"

# Azure AD Configuration
AZURE_TENANT_ID=$tenantId
AZURE_CLIENT_ID=$clientId
AZURE_CLIENT_SECRET=$clientSecret
AZURE_SUBSCRIPTION_ID=$subscriptionId
"@
        
        if ($envContent -match "# Azure AD Configuration[\s\S]*?(?=\n\n|$)") {
            $envContent = $envContent -replace "# Azure AD Configuration[\s\S]*?(?=\n\n|$)", $envUpdates.Trim()
        } else {
            $envContent += $envUpdates
        }
        
        Set-Content $envPath $envContent
        Write-Host "`nUpdated .env file with Azure configuration" -ForegroundColor Green
    }

    # Display configuration
    Write-Host "`nAzure AD Configuration:" -ForegroundColor Cyan
    Write-Host "Tenant ID: $tenantId"
    Write-Host "Client ID: $clientId"
    Write-Host "Client Secret: $($clientSecret.Substring(0,4))..." -NoNewline
    Write-Host " (saved to .env file)" -ForegroundColor Yellow
    Write-Host "Subscription ID: $subscriptionId"

    Write-Host "`nSetup completed successfully!" -ForegroundColor Green
    Write-Host "You can now use these credentials for Azure AD integration." -ForegroundColor Green

} catch {
    Write-Host "`nError: $_" -ForegroundColor Red
    Write-Host "Stack Trace: $($_.ScriptStackTrace)" -ForegroundColor Red
    exit 1
} 