$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot '.venv-build\Scripts\python.exe'
if (Test-Path $venvPython) { $python = $venvPython } else { $python = 'py'; $pyArgs = @('-3.12') }
$oldPlatform = $env:QT_QPA_PLATFORM
try {
    $env:QT_QPA_PLATFORM = 'offscreen'
    & $python @pyArgs -m unittest -v test_native_prod_parity test_checkprod_34_static test_native_ui_static test_prod_native_layout
    if ($LASTEXITCODE -ne 0) { throw 'UI or Prod test failed. No EXE was built.' }
    Write-Host 'ALL TESTS PASSED - NO EXE WAS BUILT'
} finally {
    $env:QT_QPA_PLATFORM = $oldPlatform
}
