# Local Development Script
# Starts backend and frontend concurrently for local testing

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Local Development Environment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env files exist
$backendEnv = Join-Path $RepoRoot "backend\.env"
$frontendEnv = Join-Path $RepoRoot "frontend\.env.local"

if (-not (Test-Path $backendEnv)) {
    Write-Host "[!] backend\.env not found" -ForegroundColor Yellow
    Write-Host "    Copy backend\.env.example to backend\.env and add your keys" -ForegroundColor Yellow
    $createExample = Read-Host "Create from .env.example now? (y/n)"
    if ($createExample -eq "y") {
        Copy-Item (Join-Path $RepoRoot "backend\.env.example") $backendEnv
        Write-Host "    Created backend\.env - please edit and add your keys" -ForegroundColor Green
    }
}

if (-not (Test-Path $frontendEnv)) {
    Write-Host "[!] frontend\.env.local not found" -ForegroundColor Yellow
    Write-Host "    Creating with local backend URL..." -ForegroundColor Yellow
    @"
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key
"@ | Out-File -FilePath $frontendEnv -Encoding UTF8
    Write-Host "    Created frontend\.env.local - please edit and add your Supabase keys" -ForegroundColor Green
}

# Function to start backend
function Start-Backend {
    Write-Host ""
    Write-Host "[Backend] Starting on port 8000..." -ForegroundColor Green
    
    $backendPath = Join-Path $RepoRoot "backend"
    
    # Check for virtual environment
    $venvPath = Join-Path $backendPath "venv\Scripts\Activate.ps1"
    
    $backendCmd = @"
cd '$backendPath'
if (Test-Path '$venvPath') { & '$venvPath' }
Write-Host 'Installing dependencies...' -ForegroundColor Gray
pip install -r requirements.txt -q
Write-Host 'Starting uvicorn...' -ForegroundColor Green
uvicorn main:app --reload --port 8000
"@
    
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd
}

# Function to start frontend
function Start-Frontend {
    Write-Host ""
    Write-Host "[Frontend] Starting on port 3000..." -ForegroundColor Blue
    
    $frontendPath = Join-Path $RepoRoot "frontend"
    
    $frontendCmd = @"
cd '$frontendPath'
Write-Host 'Installing dependencies...' -ForegroundColor Gray
npm install --silent
Write-Host 'Starting Next.js dev server...' -ForegroundColor Blue
npm run dev
"@
    
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd
}

# Start services based on flags
if ($BackendOnly) {
    Start-Backend
}
elseif ($FrontendOnly) {
    Start-Frontend
}
else {
    Start-Backend
    Start-Sleep -Seconds 2
    Start-Frontend
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Services Starting..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor Blue
Write-Host "  Swagger:  http://localhost:8000/docs" -ForegroundColor Gray
Write-Host ""
Write-Host "  Press Ctrl+C in each terminal to stop" -ForegroundColor DarkGray
Write-Host ""

# Wait a bit then open browser
Start-Sleep -Seconds 5
Write-Host "Opening browser..." -ForegroundColor Gray
Start-Process "http://localhost:3000"
