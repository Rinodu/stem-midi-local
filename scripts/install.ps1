param([string]$RuntimeRoot)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
function Check-Exit { if ($LASTEXITCODE -ne 0) { throw "Perintah instalasi gagal (exit $LASTEXITCODE)." } }
if (-not $RuntimeRoot) { $RuntimeRoot = (Get-Location).Path }
$RuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot)
$venvPath = Join-Path $RuntimeRoot '.venv'
$pythonPath = Join-Path $venvPath 'Scripts\python.exe'
$runtimeLocal = Join-Path $RuntimeRoot '.local'
New-Item -ItemType Directory -Path $runtimeLocal -Force | Out-Null
$env:UV_CACHE_DIR = Join-Path $runtimeLocal 'cache'
$env:TEMP = Join-Path $runtimeLocal 'temp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
$volume = Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($RuntimeRoot).TrimEnd('\').TrimEnd(':'))
if (-not (Test-Path -LiteralPath (Join-Path $venvPath 'Lib\site-packages\torch\__init__.py')) -and $volume.Free -lt 12GB) {
    throw 'Siapkan minimal 12 GB kosong, atau jalankan Install.bat -RuntimeRoot E:\StemMidiRuntime pada drive yang cukup.'
}
if (-not (Test-Path -LiteralPath $pythonPath)) {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        uv python install 3.10
        Check-Exit
        uv venv --python 3.10 $venvPath
        Check-Exit
    } else {
        py -3.10 -m venv $venvPath
        Check-Exit
    }
}
& $pythonPath -c "import sys; assert sys.version_info[:2] == (3, 10), 'Environment harus Python 3.10'"
Check-Exit
& $pythonPath -m ensurepip --upgrade
Check-Exit
& $pythonPath -m pip install --upgrade pip
Check-Exit
if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv pip install --python $pythonPath torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121
} else {
    & $pythonPath -m pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121
}
Check-Exit
if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv pip install --python $pythonPath -r requirements.txt
} else {
    & $pythonPath -m pip install -r requirements.txt
}
Check-Exit
& $pythonPath -m pip check
Check-Exit
& $pythonPath -m pytest -q
Check-Exit
New-Item -ItemType Directory -Path '.local' -Force | Out-Null
Set-Content -LiteralPath '.local\runtime.txt' -Value $RuntimeRoot -Encoding UTF8
