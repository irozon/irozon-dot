[CmdletBinding()]
param([string]$Executable,
      [string]$Destination = (Join-Path $env:LOCALAPPDATA 'Programs\Irozon Dot'),
      [string]$ShortcutsDirectory = [Environment]::GetFolderPath('Desktop'))
$ErrorActionPreference = 'Stop'
if (-not $Executable) {
    $Executable = Join-Path $PSScriptRoot 'IrozonDot.exe'
    if (-not (Test-Path -LiteralPath $Executable)) {
        $project = Split-Path -Parent $PSScriptRoot
        $Executable = Join-Path $project ('dist\windows-' + (Get-Content (Join-Path $project 'VERSION') -Raw).Trim() + '\IrozonDot.exe')
    }
}
$source = (Resolve-Path -LiteralPath $Executable).Path
$bundle = Split-Path -Parent $source
# Copy only the reviewed distribution, never adjacent credentials or local settings.
$files = @('LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md', 'THIRD-PARTY-NOTICES.txt',
           'SECURITY.md', 'README.md', 'BUILD-MANIFEST.json', 'SHA256SUMS.txt')
$directories = @('docs', 'licenses', 'home-assistant')
foreach ($entry in ($files + $directories)) {
    if (-not (Test-Path -LiteralPath (Join-Path $bundle $entry))) {
        throw 'The complete Windows release bundle is required, including notices and documentation. No installation changes were made.'
    }
}
# Require the exported example; do not copy a user's adjacent Home Assistant secrets.
$haExample = Join-Path $bundle 'home-assistant\irozon-dot.example.yaml'
if (-not (Test-Path -LiteralPath $haExample)) { throw 'The public Home Assistant example is missing.' }
$names = @('Irozon Dot Companion','Irozon Dot Settings','Stop Irozon Dot Companion','Restart Irozon Dot Companion')
$desktop = $ShortcutsDirectory
foreach ($name in $names) {
    if (Test-Path -LiteralPath (Join-Path $desktop ($name + '.lnk'))) {
        throw 'A desktop control already exists. No installation changes were made.'
    }
}
if (Test-Path -LiteralPath (Join-Path $Destination 'IrozonDot.exe')) {
    throw 'An executable is already installed. Stop it and explicitly replace/update it; this installer will not overwrite it.'
}
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
Copy-Item -LiteralPath $source -Destination (Join-Path $Destination 'IrozonDot.exe')
foreach ($entry in $files) {
    Copy-Item -LiteralPath (Join-Path $bundle $entry) -Destination (Join-Path $Destination $entry)
}
foreach ($entry in @('docs', 'licenses')) {
    Copy-Item -LiteralPath (Join-Path $bundle $entry) -Destination $Destination -Recurse
}
New-Item -ItemType Directory -Path (Join-Path $Destination 'home-assistant') -Force | Out-Null
Copy-Item -LiteralPath $haExample -Destination (Join-Path $Destination 'home-assistant\irozon-dot.example.yaml')
New-Item -ItemType Directory -Path $desktop -Force | Out-Null
$shell = New-Object -ComObject WScript.Shell
foreach ($entry in @(@('Irozon Dot Companion','start'), @('Irozon Dot Settings','settings'),
                     @('Stop Irozon Dot Companion','stop'), @('Restart Irozon Dot Companion','restart'))) {
    $shortcutPath = Join-Path $desktop ($entry[0] + '.lnk')
    if (Test-Path -LiteralPath $shortcutPath) { throw 'Desktop shortcut already exists; no shortcut was overwritten' }
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $Destination 'IrozonDot.exe'
    $shortcut.Arguments = $entry[1]
    $shortcut.WorkingDirectory = $Destination
    $shortcut.Description = 'Irozon Dot standalone Windows companion'
    $shortcut.Save()
}
Write-Output 'Installed executable, notices, documentation and desktop controls. Not launched. Startup remains opt-in in Settings.'
