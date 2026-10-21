[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$releaseVersion = (Get-Content -LiteralPath (Join-Path $project 'VERSION') -Raw).Trim()
$releaseOutput = Join-Path $project ('dist\windows-' + $releaseVersion)
$buildPython = Join-Path $project '.pio\companion-build\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $buildPython)) {
    & python -m venv (Join-Path $project '.pio\companion-build')
    if ($LASTEXITCODE -ne 0) { throw 'Build environment creation failed' }
}
& $buildPython -m pip install -r (Join-Path $PSScriptRoot 'requirements-build.txt')
if ($LASTEXITCODE -ne 0) { throw 'Build dependencies failed' }
$previousPath = $env:PATH
try {
    $pythonBase = (& $buildPython -c 'import sys; print(sys.base_prefix)').Trim()
    $env:PATH = "$pythonBase;$pythonBase\DLLs;$env:SystemRoot\System32;$env:SystemRoot"
    & $buildPython -m PyInstaller --clean --noconfirm --distpath $releaseOutput `
        --workpath (Join-Path $project '.pio\companion-pyinstaller') (Join-Path $PSScriptRoot 'IrozonDot.spec')
    if ($LASTEXITCODE -ne 0) { throw 'Executable build failed' }
} finally { $env:PATH = $previousPath }
& $buildPython (Join-Path $project 'scripts\audit_companion_package.py') --executable (Join-Path $releaseOutput 'IrozonDot.exe')
if ($LASTEXITCODE -ne 0) { throw 'Package privacy audit failed' }
Write-Output "Built $releaseOutput\IrozonDot.exe. No installation, startup changes, or launch performed."
