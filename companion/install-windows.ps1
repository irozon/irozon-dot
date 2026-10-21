[CmdletBinding()]
param([switch]$NoStartup)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = (& python -c 'import sys; print(sys.executable)').Trim()
if ($LASTEXITCODE -ne 0) { throw 'Python installation not found' }
$pythonw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonw)) { throw 'pythonw.exe is required' }
$launcher = Join-Path $PSScriptRoot 'background.pyw'
$shell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
function Add-IrozonShortcut([string]$Directory, [string]$Name, [string]$Action) {
    $shortcut = $shell.CreateShortcut((Join-Path $Directory ($Name + '.lnk')))
    $shortcut.TargetPath = $pythonw
    $shortcut.Arguments = '"' + $launcher + '" ' + $Action
    $shortcut.WorkingDirectory = $root
    $shortcut.Description = 'Irozon Dot Codex usage companion - ' + $Action
    $shortcut.WindowStyle = 7
    $shortcut.Save()
}
Add-IrozonShortcut $desktop 'Irozon Dot' 'start'
Add-IrozonShortcut $desktop 'Stop Irozon Dot' 'stop'
Add-IrozonShortcut $desktop 'Restart Irozon Dot' 'restart'
Write-Output 'Installed Start, Stop and Restart desktop shortcuts (pythonw.exe; no console).'
if (-not $NoStartup) {
    $user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $monitor = Join-Path $PSScriptRoot 'monitor.py'
    $action = New-ScheduledTaskAction -Execute $pythonw -Argument ('"' + $monitor + '" --background') -WorkingDirectory $root
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
    $trigger.Delay = 'PT20S'
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable `
        -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    try {
        Register-ScheduledTask -TaskName 'Irozon Dot' -Action $action -Trigger $trigger `
            -Principal $principal -Settings $settings -Description 'Silent per-user Codex usage companion' -Force | Out-Null
        Write-Output 'Enabled Task Scheduler sign-in startup (interactive user, limited privileges, 20 s delay).'
    } catch {
        $startup = [Environment]::GetFolderPath('Startup')
        Add-IrozonShortcut $startup 'Irozon Dot' 'start'
        Write-Output ('Task Scheduler registration unavailable: ' + $_.Exception.Message)
        Write-Output 'Enabled equivalent per-user Startup-folder shortcut instead; no elevation required.'
    }
}
Write-Output 'Installation does not start or stop the companion. Use the desktop shortcuts.'
