# ops/windows/install-scheduled-task.ps1
# One-shot installer: register Windows Scheduled Task that runs the NEV daily pipeline at 06:00.
#
# All identifiers/messages kept ASCII so the script is encoding-agnostic on
# Chinese-locale PowerShell (which reads .ps1 as GBK by default — non-ASCII
# Chinese in this file would be mojibake'd, breaking TaskName lookups).

$TaskName    = "NEV-Daily-Brief"
$ProjectRoot = "D:\Newclaude\nev-brief"
$Runner      = Join-Path $ProjectRoot "ops\windows\run-daily.ps1"

if (-not (Test-Path $Runner)) {
    Write-Error "Runner script not found at $Runner"
    exit 1
}

# Cleanup: remove the current task name AND any previously-installed garbled
# variants (older versions of this script used a Chinese name that turned into
# mojibake on Chinese-locale PowerShell). Pattern matches both.
Get-ScheduledTask -ErrorAction SilentlyContinue |
    Where-Object { $_.TaskName -eq $TaskName -or $_.TaskName -like "NEV*Daily" } |
    ForEach-Object {
        Write-Host "Removing previous task: $($_.TaskName)"
        Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false -ErrorAction SilentlyContinue
    }

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`"" `
    -WorkingDirectory $ProjectRoot

$trigger = New-ScheduledTaskTrigger -Daily -At "06:00AM"

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "NEV morning brief: daily 06:00 full pipeline (crawl > pipeline > summarize > compose > deliver)"

Write-Host ""
Write-Host "OK: scheduled task '$TaskName' installed for daily 06:00"
Write-Host "Test it manually with:"
Write-Host "    Start-ScheduledTask -TaskName `"$TaskName`""
Write-Host "Logs at: $ProjectRoot\logs\daily-YYYYMMDD.log"
