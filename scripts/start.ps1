$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$runtimeRoot = (Get-Location).Path
if (Test-Path -LiteralPath '.local\runtime.txt') {
    $runtimeRoot = (Get-Content -LiteralPath '.local\runtime.txt' -Raw).Trim()
}
$pythonPath = Join-Path $runtimeRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Jalankan Install.bat terlebih dahulu.' }
& $pythonPath scripts\launch.py
if ($LASTEXITCODE -ne 0) { throw 'Launcher berhenti dengan error. Periksa pesan di atas.' }
