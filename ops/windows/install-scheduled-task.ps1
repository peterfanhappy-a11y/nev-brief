# ops/windows/install-scheduled-task.ps1
# 一次性运行：注册 Windows Scheduled Task 每天 06:00 跑 NEV daily。

$TaskName = "NEV 早报 Daily"
$ProjectRoot = "D:\Newclaude\nev-brief"
$Runner = Join-Path $ProjectRoot "ops\windows\run-daily.ps1"

if (-not (Test-Path $Runner)) {
    Write-Error "Runner script not found at $Runner"
    exit 1
}

# 删除旧任务（如果存在）
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

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
    -Description "NEV 早报：每日 06:00 全 pipeline 执行 (crawl > pipeline > summarize > compose > deliver)"

Write-Host "OK: scheduled task '$TaskName' installed for daily 06:00"
Write-Host "Test it manually with:"
Write-Host "    Start-ScheduledTask -TaskName `"$TaskName`""
Write-Host "Logs at: $ProjectRoot\logs\daily-YYYYMMDD.log"
