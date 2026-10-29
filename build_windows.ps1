$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if ($env:OS -ne 'Windows_NT') { throw 'Build nay can Windows 10/11 64-bit.' }
if (-not (Test-Path 'app.ico')) { throw 'Can app.ico cung thu muc launcher.py.' }
py -3.12 -m venv .venv-build
if ($LASTEXITCODE -ne 0) { throw 'Can Python 3.12 64-bit tren may build.' }
$python = Join-Path $PSScriptRoot '.venv-build\Scripts\python.exe'
& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Khong cap nhat duoc pip.' }
& $python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Cai dependency that bai.' }
& $python -m unittest test_native_cot test_theme test_release33 test_sku_finder test_bridge34 test_native_ui_static test_area_buttons_release34 test_chrome_persistent test_auto_hide_reconnect
if ($LASTEXITCODE -ne 0) { throw 'COT behavior verification failed.' }
# Limit DLL discovery to this Python installation and Windows. Unrelated tools
# on PATH can otherwise inject incompatible ICU/OpenSSL/UCRT DLLs into the EXE.
$buildPathBefore = $env:PATH
$buildPythonBase = (& $python -c "import sys; print(sys.base_prefix)").Trim()
try {
    $env:PATH = @((Split-Path $python), $buildPythonBase, (Join-Path $buildPythonBase 'Scripts'),
                  (Join-Path $env:SystemRoot 'System32'), $env:SystemRoot) -join ';'
    & $python -m PyInstaller --noconfirm --clean --onefile --windowed --name "IntraCity 3.4" --icon "app.ico" --add-data "app.ico;." --add-data "wms_bridge_manifest.json;." --add-data "wms_bridge_background.js;." --add-data "wms_bridge_content.js;." --add-data "wms_bridge_popup.html;." --add-data "wms_bridge_popup.js;." --add-data "wms_bridge_icon.png;." --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebChannel --collect-all playwright --hidden-import psutil --hidden-import python_calamine --hidden-import pandas.io.excel._calamine --hidden-import openpyxl --hidden-import xlrd launcher.py
    if ($LASTEXITCODE -ne 0) { throw 'Build EXE that bai.' }
} finally {
    $env:PATH = $buildPathBefore
}
if (-not (Test-Path 'dist\IntraCity 3.4.exe')) { throw 'Khong tim thay EXE dau ra.' }
$process = Start-Process -WindowStyle Hidden -FilePath '.\dist\IntraCity 3.4.exe' -ArgumentList '--smoke-test' -PassThru
if (-not $process.WaitForExit(120000)) {
    $process.Kill()
    throw 'EXE startup test timed out.'
}
if ($process.ExitCode -ne 0) { throw 'EXE startup test failed.' }
if (-not (Test-Path 'smoke-test-result.json')) { throw 'EXE did not produce a startup test result.' }
$result = Get-Content 'smoke-test-result.json' -Raw | ConvertFrom-Json
if (-not $result.passed) { throw 'EXE GUI / Playwright driver verification failed.' }
Write-Host 'Xong: dist\IntraCity 3.4.exe'




& $python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw 'Cannot install test browser.' }
& $python test_extension_windows.py 'dist\IntraCity 3.4.exe'
if ($LASTEXITCODE -ne 0) { throw 'Packaged extension bridge verification failed.' }
