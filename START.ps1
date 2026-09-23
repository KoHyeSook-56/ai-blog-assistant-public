$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Join-Path $PSScriptRoot 'backend')
$appPython = Join-Path $PSScriptRoot 'backend/.venv/Scripts/python.exe'
try {
    $runningApp = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2
    if ($runningApp.status -eq 'ok') { Start-Process 'http://127.0.0.1:8765'; exit 0 }
} catch { }
if (-not (Test-Path -LiteralPath $appPython)) {
    $preparedPython = Join-Path $PSScriptRoot '../../work/blog-venv/Scripts/python.exe'
    if (Test-Path -LiteralPath $preparedPython) { $appPython = (Resolve-Path -LiteralPath $preparedPython).Path }
}
if (-not (Test-Path -LiteralPath $appPython)) {
    Write-Host 'The application environment is not installed yet. See README.md. No installation is performed by this launcher.'
    Read-Host 'Press Enter to close'
    exit 1
}
& $appPython -c 'import fastapi, uvicorn, firebase_admin, openai, dotenv'
if ($LASTEXITCODE -ne 0) { Read-Host 'Dependencies are missing. Press Enter to close'; exit 1 }
Start-Process 'http://127.0.0.1:8765'
& $appPython -m uvicorn main:app --host 127.0.0.1 --port 8765 --workers 1
