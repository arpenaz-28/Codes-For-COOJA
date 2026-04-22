# 05-orchestrate-from-laptop.ps1
#
# Full automated LAAKA hardware simulation orchestration.
#
# TOPOLOGY
#   Laptop          = Registration Authority (RA)  port 5683  — gw_hw.py runs HERE
#   RPi #1 (apex@192.168.1.132) = Fog Auth Server  port 5684  — as_hw.py
#   RPi #2 (pi@192.168.1.113)   = Device Node       port 5685  — node_hw.py
#
# WHAT THIS SCRIPT DOES
#   1.  Deploy the project to both RPis via SCP
#   2.  Install pycryptodome on both RPis (idempotent)
#   3.  Start Fog server   on RPi #1 via SSH (stdout → results\fog.log)
#   4.  Start RA           on THIS laptop    (stdout → results\ra.log)
#   5.  Start Device Node  on RPi #2 via SSH (stdout → results\node.log)
#   6.  Wait for Node to complete
#   7.  Give Fog 3 s to flush its last DATA log line, then kill all processes
#   8.  Parse HW_METRIC lines from all three logs into results\hw_metrics.csv
#   9.  Print a final summary table
#
# USAGE
#   cd "c:\ANUP\MTP\Proposing\Codes For COOJA\Hardware\LAAKA"
#   .\scripts\05-orchestrate-from-laptop.ps1
#
#   Optional override:
#   .\scripts\05-orchestrate-from-laptop.ps1 -RolesFile ".\config\roles.env"

Param(
  [string]$RolesFile = "$PSScriptRoot\..\config\roles.env"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "=== $msg ===" -ForegroundColor Cyan
}

function Read-EnvFile([string]$path) {
    $map = @{}
    Get-Content $path | Where-Object { $_ -and -not $_.TrimStart().StartsWith("#") } | ForEach-Object {
        if ($_ -match "^([^=]+)=(.*)$") {
            $map[$Matches[1].Trim()] = $Matches[2].Trim()
        }
    }
    return $map
}

# ---------------------------------------------------------------------------
# Load config
# ---------------------------------------------------------------------------
if (-not (Test-Path $RolesFile)) {
    Write-Error "roles.env not found: $RolesFile"
    exit 1
}
$cfg = Read-EnvFile $RolesFile

$asUser    = if ($cfg["AS_USER"])   { $cfg["AS_USER"] }   else { "pi" }
$asHost    = $cfg["AS_HOST"]
$nodeUser  = if ($cfg["NODE_USER"]) { $cfg["NODE_USER"] } else { "pi" }
$nodeHost  = $cfg["NODE_HOST"]

if (-not $asHost -or -not $nodeHost) {
    Write-Error "Missing AS_HOST or NODE_HOST in roles.env"
    exit 1
}

# Remote project root on both RPis
$remoteDeploy = "~/mtp-hardware/LAAKA"

# Local paths
$LaakADir   = (Resolve-Path "$PSScriptRoot\..").Path
$NativeDir  = Join-Path $LaakADir "native"
$ResultsDir = Join-Path $LaakADir "results"
$ParseScript= Join-Path $LaakADir "scripts\06-parse-hw-metrics.py"

New-Item -ItemType Directory -Force -Path $ResultsDir | Out-Null

Write-Step "LAAKA Hardware Simulation"
Write-Host "  RA   (laptop)   : $($cfg['GW_HOST']):$($cfg['GW_PORT'])"
Write-Host "  Fog  (RPi #1)   : ${asUser}@${asHost}:$($cfg['AS_PORT'])"
Write-Host "  Node (RPi #2)   : ${nodeUser}@${nodeHost}"
Write-Host "  Results dir     : $ResultsDir"

# ---------------------------------------------------------------------------
# 1. Deploy project to both RPis
# ---------------------------------------------------------------------------
Write-Step "1/6  Deploying project to RPis"

foreach ($t in @(@{user=$asUser;host=$asHost;name="Fog RPi #1"},
                 @{user=$nodeUser;host=$nodeHost;name="Node RPi #2"})) {
    Write-Host "[deploy] $($t.name) ($($t.user)@$($t.host)) ..."
    # Create remote base dir
    ssh "$($t.user)@$($t.host)" "mkdir -p ~/mtp-hardware"
    # Copy the whole LAAKA folder (scp -r copies the folder itself)
    scp -r -q "$LaakADir" "$($t.user)@$($t.host):~/mtp-hardware/"
    Write-Host "         done."
}

# ---------------------------------------------------------------------------
# 2. Install Python dependencies on both RPis
# ---------------------------------------------------------------------------
Write-Step "2/6  Installing pycryptodome on RPis"

foreach ($t in @(@{user=$asUser;host=$asHost},@{user=$nodeUser;host=$nodeHost})) {
    Write-Host "[pip] $($t.user)@$($t.host) ..."
    ssh "$($t.user)@$($t.host)" "pip3 install pycryptodome --quiet 2>&1 | tail -2"
}

# ---------------------------------------------------------------------------
# 3. Start Fog server on RPi #1  (background SSH, stdout → fog.log)
# ---------------------------------------------------------------------------
Write-Step "3/6  Starting Fog server on RPi #1"

$fogLog  = Join-Path $ResultsDir "fog.log"
$fogProc = Start-Process -FilePath "ssh" `
    -ArgumentList "-t", "${asUser}@${asHost}", "cd $remoteDeploy && python3 -u native/as_hw.py" `
    -RedirectStandardOutput $fogLog `
    -RedirectStandardError  (Join-Path $ResultsDir "fog.err") `
    -NoNewWindow -PassThru

Write-Host "[fog] PID $($fogProc.Id) — log: $fogLog"
Start-Sleep -Seconds 3   # give socket time to bind

# ---------------------------------------------------------------------------
# 4. Start RA on this laptop  (background process, stdout → ra.log)
# ---------------------------------------------------------------------------
Write-Step "4/6  Starting RA on laptop"

$raLog  = Join-Path $ResultsDir "ra.log"
$env:PYTHONUNBUFFERED = "1"
$env:LAAKA_ROLES_FILE = (Resolve-Path $RolesFile).Path

$raProc = Start-Process -FilePath "python" `
    -ArgumentList "-u", (Join-Path $NativeDir "gw_hw.py") `
    -RedirectStandardOutput $raLog `
    -RedirectStandardError  (Join-Path $ResultsDir "ra.err") `
    -NoNewWindow -PassThru

Write-Host "[ra] PID $($raProc.Id) — log: $raLog"
Start-Sleep -Seconds 2   # give RA socket time to bind

# ---------------------------------------------------------------------------
# 5. Start Device Node on RPi #2  (foreground-like SSH, stdout → node.log)
# ---------------------------------------------------------------------------
Write-Step "5/6  Starting Device Node on RPi #2"

$nodeLog  = Join-Path $ResultsDir "node.log"
$nodeProc = Start-Process -FilePath "ssh" `
    -ArgumentList "-t", "${nodeUser}@${nodeHost}", "cd $remoteDeploy && python3 -u native/node_hw.py" `
    -RedirectStandardOutput $nodeLog `
    -RedirectStandardError  (Join-Path $ResultsDir "node.err") `
    -NoNewWindow -PassThru

Write-Host "[node] PID $($nodeProc.Id) — log: $nodeLog"

# ---------------------------------------------------------------------------
# 6. Wait for Node to finish (timeout = 10 packets × interval + 60 s slack)
# ---------------------------------------------------------------------------
$sendCount    = [int]$cfg["NODE_SEND_COUNT"]
$sendInterval = [double]$cfg["NODE_SEND_INTERVAL_S"]
$timeoutMs    = [int](($sendCount * $sendInterval + 90) * 1000)

Write-Host ""
Write-Host "[wait] Node running — $sendCount packets x ${sendInterval}s interval"
Write-Host "       Timeout: $([math]::Round($timeoutMs/1000)) s"
Write-Host "       Streaming node log (Ctrl-C to abort):"
Write-Host ""

$elapsed = 0
$dotInterval = 5000   # print a progress dot every 5 s
while (-not $nodeProc.HasExited) {
    Start-Sleep -Milliseconds 500
    $elapsed += 500
    if ($elapsed % $dotInterval -eq 0) {
        $lines = if (Test-Path $nodeLog) { (Get-Content $nodeLog).Count } else { 0 }
        Write-Host "  [${elapsed}ms] node.log = $lines lines"
    }
    if ($elapsed -ge $timeoutMs) {
        Write-Warning "[wait] Node timed out — killing"
        $nodeProc.Kill()
        break
    }
}

Write-Host ""
if ($nodeProc.ExitCode -eq 0) {
    Write-Host "[node] Completed successfully (exit 0)." -ForegroundColor Green
} else {
    Write-Warning "[node] Exited with code $($nodeProc.ExitCode)"
}

# ---------------------------------------------------------------------------
# 7. Give Fog 3 s to flush last DATA line, then kill Fog + RA
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[cleanup] Waiting 3 s for Fog to flush final DATA line ..."
Start-Sleep -Seconds 3

foreach ($proc in @($fogProc, $raProc)) {
    if (-not $proc.HasExited) {
        try { $proc.Kill() } catch {}
        try { $proc.WaitForExit(3000) | Out-Null } catch {}
    }
}
Write-Host "[cleanup] Fog and RA terminated."

# ---------------------------------------------------------------------------
# 8. Parse HW_METRIC lines from all three logs
# ---------------------------------------------------------------------------
Write-Step "6/6  Parsing metrics"

$csvFiles = @()
foreach ($role in @("node","fog","ra")) {
    $logFile = Join-Path $ResultsDir "$role.log"
    $csvFile = Join-Path $ResultsDir "hw_metrics_$role.csv"
    if (Test-Path $logFile) {
        Write-Host "[parse] $role.log ..."
        $res = python $ParseScript $logFile $csvFile 2>&1
        Write-Host "        $res"
        if (Test-Path $csvFile) { $csvFiles += $csvFile }
    } else {
        Write-Warning "[parse] $role.log not found — skipping"
    }
}

# Combine all per-role CSVs into one hw_metrics.csv
$combinedCsv = Join-Path $ResultsDir "hw_metrics.csv"
if ($csvFiles.Count -gt 0) {
    $header  = Get-Content $csvFiles[0] | Select-Object -First 1
    $allRows = @($header)
    foreach ($f in $csvFiles) {
        $rows = Get-Content $f | Select-Object -Skip 1
        $allRows += $rows
    }
    $allRows | Out-File $combinedCsv -Encoding utf8
    Write-Host "[parse] Combined CSV: $combinedCsv"
}

# ---------------------------------------------------------------------------
# 9. Print logs + final summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host ("=" * 70) -ForegroundColor Yellow
Write-Host "RESULTS — LAAKA Hardware Simulation" -ForegroundColor Yellow
Write-Host ("=" * 70) -ForegroundColor Yellow

foreach ($role in @("ra","fog","node")) {
    $logFile = Join-Path $ResultsDir "$role.log"
    if (Test-Path $logFile) {
        Write-Host ""
        Write-Host "--- $($role.ToUpper()) LOG ($role.log) ---" -ForegroundColor Cyan
        Get-Content $logFile | Select-Object -Last 30 | ForEach-Object {
            if ($_ -match "^HW_METRIC\|") {
                Write-Host $_ -ForegroundColor Green
            } else {
                Write-Host $_
            }
        }
    }
}

if (Test-Path $combinedCsv) {
    Write-Host ""
    Write-Host "--- METRICS SUMMARY (hw_metrics.csv) ---" -ForegroundColor Cyan
    Get-Content $combinedCsv | ForEach-Object { Write-Host $_ }
}

Write-Host ""
Write-Host "All logs and metrics saved to: $ResultsDir" -ForegroundColor Green
Write-Host ""
