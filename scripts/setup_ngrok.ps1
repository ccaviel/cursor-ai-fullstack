# Download and setup ngrok
$ngrokZip = "ngrok-v3-stable-windows-amd64.zip"
$ngrokUrl = "https://bin.equinox.io/c/bNyj1mQVY4c/$ngrokZip"
$ngrokPath = Join-Path $PSScriptRoot "ngrok.exe"

Write-Host "`nSetting up ngrok..." -ForegroundColor Cyan

# Download ngrok if not exists
if (-not (Test-Path $ngrokPath)) {
    Write-Host "Downloading ngrok..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $ngrokUrl -OutFile (Join-Path $PSScriptRoot $ngrokZip)
    Expand-Archive -Path (Join-Path $PSScriptRoot $ngrokZip) -DestinationPath $PSScriptRoot -Force
    Remove-Item (Join-Path $PSScriptRoot $ngrokZip)
}

# Configure ngrok with auth token
Write-Host "`nConfiguring ngrok..." -ForegroundColor Yellow
$authToken = "2tSvYRyShdiZTLR0ChBaewTBfYV_7GQJ2RudtgCt4SNvzbagK"
& $ngrokPath config add-authtoken $authToken

# Save token to .env file
$envPath = Join-Path $PSScriptRoot "../.env"
if (Test-Path $envPath) {
    $envContent = Get-Content $envPath -Raw
    if ($envContent -notmatch "NGROK_AUTH_TOKEN=") {
        Add-Content $envPath "`nNGROK_AUTH_TOKEN=$authToken"
    }
}

# Check if ngrok is running
$ngrokProcess = Get-Process ngrok -ErrorAction SilentlyContinue
if ($ngrokProcess) {
    Write-Host "ngrok is already running, stopping it..." -ForegroundColor Yellow
    $ngrokProcess | Stop-Process -Force
}

# Start ngrok
Write-Host "`nStarting ngrok tunnel to localhost:8081..." -ForegroundColor Yellow
Start-Process -FilePath $ngrokPath -ArgumentList "http", "8081" -NoNewWindow

# Wait for ngrok to start
Start-Sleep -Seconds 5

# Get ngrok public URL
Write-Host "`nGetting ngrok public URL..." -ForegroundColor Yellow
$ngrokApi = "http://localhost:4040/api/tunnels"
try {
    $response = Invoke-RestMethod -Uri $ngrokApi
    $publicUrl = $response.tunnels[0].public_url
    
    Write-Host "`nngrok tunnel established!" -ForegroundColor Green
    Write-Host "Public URL: $publicUrl" -ForegroundColor Cyan
    
    # Update .env file
    if (Test-Path $envPath) {
        $envContent = Get-Content $envPath -Raw
        $envContent = $envContent -replace "WEBHOOK_PUBLIC_URL=.*", "WEBHOOK_PUBLIC_URL=$publicUrl"
        if ($envContent -notmatch "WEBHOOK_PUBLIC_URL=") {
            $envContent += "`nWEBHOOK_PUBLIC_URL=$publicUrl"
        }
        Set-Content $envPath $envContent
        Write-Host "`nUpdated .env file with ngrok URL" -ForegroundColor Green
    }
    
    Write-Host "`nYou can now run the webhook setup script to update the webhook URL." -ForegroundColor Yellow
    Write-Host "The ngrok tunnel will remain active until you close this window." -ForegroundColor Yellow
    
} catch {
    Write-Host "`nError getting ngrok URL: $_" -ForegroundColor Red
    exit 1
} 