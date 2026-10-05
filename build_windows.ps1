$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if ($env:OS -ne 'Windows_NT') { throw 'Build nay can Windows 10/11 64-bit.' }
python -m venv .venv-build
if ($LASTEXITCODE -ne 0) { throw 'Can Python 3.12 64-bit tren may build.' }
$python = Join-Path $PSScriptRoot '.venv-build\Scripts\python.exe'
& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Khong cap nhat duoc pip.' }
& $python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Cai dependency that bai.' }
& $python test_native_cot.py
if ($LASTEXITCODE -ne 0) { throw 'COT behavior verification failed.' }
& $python -m PyInstaller --noconfirm --clean --onefile --windowed --name IntraCity_2.4.1 --collect-all playwright --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtWebChannel --hidden-import openpyxl --hidden-import xlrd launcher.py
if ($LASTEXITCODE -ne 0) { throw 'Build EXE that bai.' }
if (-not (Test-Path 'dist\IntraCity_2.4.1.exe')) { throw 'Khong tim thay EXE dau ra.' }
$process = Start-Process -FilePath '.\dist\IntraCity_2.4.1.exe' -ArgumentList '--smoke-test' -PassThru
if (-not $process.WaitForExit(120000)) {
    $process.Kill()
    throw 'EXE startup test timed out.'
}
if ($process.ExitCode -ne 0) { throw 'EXE startup test failed.' }
if (-not (Test-Path 'smoke-test-result.json')) { throw 'EXE did not produce a startup test result.' }
$result = Get-Content 'smoke-test-result.json' -Raw | ConvertFrom-Json
if (-not $result.passed) { throw 'EXE GUI / Playwright driver verification failed.' }
Write-Host 'Xong: dist\IntraCity_2.4.1.exe'
