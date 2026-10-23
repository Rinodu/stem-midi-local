$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
function Check-Exit { if ($LASTEXITCODE -ne 0) { throw "Perintah instalasi gagal (exit $LASTEXITCODE)." } }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        uv python install 3.10
        Check-Exit
        uv venv --python 3.10 .venv
        Check-Exit
    } else {
        py -3.10 -m venv .venv
        Check-Exit
    }
}
$pythonPath = Join-Path (Get-Location) '.venv\Scripts\python.exe'
& $pythonPath -m ensurepip --upgrade
Check-Exit
& $pythonPath -m pip install --upgrade pip
Check-Exit
& $pythonPath -m pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121
Check-Exit
& $pythonPath -m pip install -r requirements.txt
Check-Exit
& $pythonPath -m pip check
Check-Exit
& $pythonPath -m pytest -q
Check-Exit
