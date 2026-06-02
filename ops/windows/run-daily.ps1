# ops/windows/run-daily.ps1
# 由 Windows Task Scheduler 06:00 daily 调用。

$ErrorActionPreference = "Continue"
$ProjectRoot = "D:\Newclaude\nev-brief"
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir ("daily-" + (Get-Date -Format "yyyyMMdd") + ".log")

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Set-Location $ProjectRoot

# uv 必须在 PATH 中
$UvPath = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $UvPath) {
    $UvPath = "$env:USERPROFILE\.cargo\bin\uv.exe"
}
if (-not (Test-Path $UvPath)) {
    "[$(Get-Date -Format 'u')] FATAL: uv not found" | Tee-Object -Append $LogFile
    exit 1
}

"[$(Get-Date -Format 'u')] daily run starting" | Tee-Object -Append $LogFile

& $UvPath run python -m nev_orchestrator daily 2>&1 | Tee-Object -Append $LogFile
$exitCode = $LASTEXITCODE

"[$(Get-Date -Format 'u')] daily run finished, exit=$exitCode" | Tee-Object -Append $LogFile
exit $exitCode
