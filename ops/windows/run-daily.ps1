# ops/windows/run-daily.ps1
# 由 Windows Task Scheduler 06:00 daily 调用。

$ErrorActionPreference = "Continue"
$ProjectRoot = "D:\Newclaude\nev-brief"
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir ("daily-" + (Get-Date -Format "yyyyMMdd") + ".log")

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Set-Location $ProjectRoot

# Locate uv. PATH first (rare under Task Scheduler -NoProfile), then the
# common install locations. Mirror ops/launchd/run-daily.sh.
$UvPath = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $UvPath) {
    $candidates = @(
        "$env:USERPROFILE\.local\bin\uv.exe",                # uv self-installer (most common)
        "$env:USERPROFILE\.cargo\bin\uv.exe",                # cargo install
        "$env:LOCALAPPDATA\Programs\uv\uv.exe",              # uv self-installer alt
        "$env:USERPROFILE\miniconda3\Scripts\uv.exe",        # conda base
        "$env:USERPROFILE\anaconda3\Scripts\uv.exe",         # anaconda base
        "$env:USERPROFILE\scoop\shims\uv.exe",               # scoop
        "$env:ProgramFiles\uv\uv.exe"                        # system-wide install
    )
    foreach ($cand in $candidates) {
        if (Test-Path $cand) { $UvPath = $cand; break }
    }
}
if (-not $UvPath -or -not (Test-Path $UvPath)) {
    "[$(Get-Date -Format 'u')] FATAL: uv not found in PATH or common install locations" | Tee-Object -Append $LogFile
    exit 1
}

"[$(Get-Date -Format 'u')] daily run starting" | Tee-Object -Append $LogFile

& $UvPath run python -m nev_orchestrator daily 2>&1 | Tee-Object -Append $LogFile
$exitCode = $LASTEXITCODE

"[$(Get-Date -Format 'u')] daily run finished, exit=$exitCode" | Tee-Object -Append $LogFile
exit $exitCode
