[CmdletBinding()]
param([string]$Executable = (Join-Path (Split-Path -Parent $PSScriptRoot) ('dist\windows-' + (Get-Content (Join-Path (Split-Path -Parent $PSScriptRoot) 'VERSION') -Raw).Trim() + '\IrozonDot.exe')),
      [string]$Destination = (Join-Path $env:LOCALAPPDATA 'Programs\Irozon Dot'))
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $Executable).Path
$names = @('Irozon Dot Companion','Irozon Dot Settings','Stop Irozon Dot Companion','Restart Irozon Dot Companion')
$desktop = [Environment]::GetFolderPath('Desktop')
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
Write-Output 'Installed executable and desktop controls. Not launched. Startup remains opt-in in Settings.'
