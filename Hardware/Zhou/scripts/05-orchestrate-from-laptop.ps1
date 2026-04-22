# 05-orchestrate-from-laptop.ps1
# ============================================================
# Full orchestration of the Zhou scheme hardware simulation:
#   Laptop  = GW_Server + GW_Router  (started locally)
#   RPi #1  = Sensor Node            (started via SSH)
#   RPi #2  = User Device            (started via SSH)
#
# Prerequisites:
#   - roles.env updated with correct IPs
#   - SSH key-based auth to both RPis (no password prompt)
#   - Python 3 + pycryptodome installed on both RPis and laptop
#   - Zhou folder synced to RPis (run 02-sync-project.sh first)
#
# Usage:
#   cd "Codes For COOJA\Hardware\Zhou"
#   .\scripts\05-orchestrate-from-laptop.ps1
# ============================================================
Param(
  [string]$RolesFile = "$PSScriptRoot\..\config\roles.env"
)

if (-not (Test-Path $RolesFile)) {
  Write-Error "roles.env not found: $RolesFile"
  exit 1
}

# --- Parse roles.env ---
$envText = Get-Content $RolesFile | Where-Object { $_ -and -not $_.StartsWith("#") }
$map = @{}
foreach ($line in $envText) {
  if ($line.Contains("=")) {
    $parts = $line.Split("=", 2)
    if ($parts.Count -eq 2) {
      $map[$parts[0].Trim()] = $parts[1].Trim()
    }
  }
}

$snUser    = if ($map["SN_USER"])   { $map["SN_USER"] }   else { "pi" }
$snHost    = $map["SN_HOST"]
$userUser  = if ($map["USER_USER"]) { $map["USER_USER"] } else { "pi" }
$userHost  = $map["USER_HOST"]

if (-not $snHost -or -not $userHost) {
  Write-Error "Missing SN_HOST or USER_HOST in roles.env"
  exit 1
}

$remoteBase = $map["REMOTE_BASE_DIR"]
$projDir    = $map["PROJECT_DIR_NAME"]   # "Zhou"
$remoteScripts = "$remoteBase/$projDir/scripts"

# --- Results directory ---
$resultsDir = "$PSScriptRoot\..\results"
New-Item -ItemType Directory -Force -Path $resultsDir | Out-Null

$gwSrvLog  = "$resultsDir\gw_server.log"
$gwRtrLog  = "$resultsDir\gw_router.log"
$snLog     = "$resultsDir\sn.log"
$userLog   = "$resultsDir\user.log"

Write-Host ""
Write-Host "============================================================"
Write-Host " Zhou Scheme Hardware Simulation — Orchestration"
Write-Host "============================================================"
Write-Host " SN    : $snUser@$snHost"
Write-Host " User  : $userUser@$userHost"
Write-Host " Logs  : $resultsDir"
Write-Host "============================================================"
Write-Host ""

# --- Step 1: Start GW_Server locally (background job) ---
Write-Host "[1/4] Starting GW_Server on laptop..."
$gwSrvJob = Start-Job -ScriptBlock {
  param($scriptDir, $log)
  & bash "$scriptDir/04-run-role.sh" gw_server 2>&1 | Tee-Object -FilePath $log
} -ArgumentList $PSScriptRoot, $gwSrvLog
Write-Host "      GW_Server started (Job ID $($gwSrvJob.Id)) → log: $gwSrvLog"
Start-Sleep -Seconds 1

# --- Step 2: Start GW_Router locally (background job) ---
Write-Host "[2/4] Starting GW_Router on laptop..."
$gwRtrJob = Start-Job -ScriptBlock {
  param($scriptDir, $log)
  & bash "$scriptDir/04-run-role.sh" gw_router 2>&1 | Tee-Object -FilePath $log
} -ArgumentList $PSScriptRoot, $gwRtrLog
Write-Host "      GW_Router started (Job ID $($gwRtrJob.Id)) → log: $gwRtrLog"
Start-Sleep -Seconds 1

# --- Step 3: Start Sensor Node on RPi #1 (background SSH) ---
Write-Host "[3/4] Starting Sensor Node on $snHost..."
$snJob = Start-Job -ScriptBlock {
  param($user, $host, $scripts, $log)
  ssh "${user}@${host}" "cd $scripts && chmod +x *.sh && ./04-run-role.sh sn 2>&1" |
    Tee-Object -FilePath $log
} -ArgumentList $snUser, $snHost, $remoteScripts, $snLog
Write-Host "      SN started (Job ID $($snJob.Id)) → log: $snLog"

# --- Step 4: Start User Device on RPi #2 (foreground SSH — this drives completion) ---
Write-Host "[4/4] Starting User Device on $userHost  (foreground — drives the simulation)..."
Write-Host "      Log: $userLog"
Write-Host ""
Write-Host "  Waiting for simulation to complete..."
Write-Host "  (User will wait 10 s for SN to register, then run full protocol)"
Write-Host ""

ssh "${userUser}@${userHost}" "cd $remoteScripts && chmod +x *.sh && ./04-run-role.sh user 2>&1" |
  Tee-Object -FilePath $userLog

Write-Host ""
Write-Host "============================================================"
Write-Host " User finished. Stopping GW_Server and GW_Router..."
Write-Host "============================================================"

# Allow SN to finish printing its final metric report
Start-Sleep -Seconds 5

# Stop background jobs
Stop-Job  $gwSrvJob, $gwRtrJob, $snJob -ErrorAction SilentlyContinue
Remove-Job $gwSrvJob, $gwRtrJob, $snJob -ErrorAction SilentlyContinue

# Also ask SN RPi to stop (if still running)
ssh "${snUser}@${snHost}" "pkill -f sn_hw.py 2>/dev/null; true"

Write-Host ""
Write-Host "============================================================"
Write-Host " Parsing metrics..."
Write-Host "============================================================"

# Parse metrics from SN and User logs
$parseScript = "$PSScriptRoot\06-parse-hw-metrics.py"
if (Test-Path $parseScript) {
  $snCsv   = "$resultsDir\hw_metrics_sn.csv"
  $userCsv = "$resultsDir\hw_metrics_user.csv"
  & python3 $parseScript $snLog   $snCsv
  & python3 $parseScript $userLog $userCsv
  Write-Host "  SN   metrics → $snCsv"
  Write-Host "  User metrics → $userCsv"
} else {
  Write-Host "  (06-parse-hw-metrics.py not found — skipping CSV export)"
}

Write-Host ""
Write-Host "Done!  Check logs in: $resultsDir"
Write-Host ""
Write-Host "NEXT STEP: review hw_metrics_user.csv and hw_metrics_sn.csv"
Write-Host "           for wall_s / cpu_s / energy_j per phase."
