# 05-orchestrate-from-laptop.ps1
#
# Orchestrate the Revised-Anonymity hardware run from the laptop.
# Starts AS on RPi #1 and Node on RPi #2 via SSH, then prompts
# you to start the GW locally.
#
# Usage (PowerShell):
#   .\scripts\05-orchestrate-from-laptop.ps1
#   .\scripts\05-orchestrate-from-laptop.ps1 -RolesFile "C:\path\to\roles.env"

Param(
  [string]$RolesFile = "$PSScriptRoot\..\config\roles.env"
)

if (-not (Test-Path $RolesFile)) {
  Write-Error "roles.env not found: $RolesFile"
  exit 1
}

# Parse roles.env into a hashtable
$envText = Get-Content $RolesFile | Where-Object { $_ -and -not $_.TrimStart().StartsWith("#") }
$map = @{}
foreach ($line in $envText) {
  if ($line.Contains("=")) {
    $parts = $line.Split("=", 2)
    if ($parts.Count -eq 2) {
      $map[$parts[0].Trim()] = $parts[1].Trim()
    }
  }
}

$asUser    = $map["AS_USER"]
$asHost    = $map["AS_HOST"]
$nodeUser  = $map["NODE_USER"]
$nodeHost  = $map["NODE_HOST"]
$remoteBase = $map["REMOTE_BASE_DIR"]
$projectDir = $map["PROJECT_DIR_NAME"]

if (-not $asHost -or -not $nodeHost) {
  Write-Error "Missing AS_HOST or NODE_HOST in roles.env"
  exit 1
}

if (-not $asUser)   { $asUser   = "pi" }
if (-not $nodeUser) { $nodeUser = "pi" }

$remoteScripts = "$remoteBase/$projectDir/scripts"

Write-Host ""
Write-Host "=== Revised-Anonymity Hardware Orchestration ==="
Write-Host "  GW   : this laptop (run GW locally after this script)"
Write-Host "  AS   : $asUser@$asHost"
Write-Host "  Node : $nodeUser@$nodeHost"
Write-Host ""

# Step 1: Start AS on RPi #1 (background SSH)
Write-Host "[orchestrate] Starting AS on $asHost ..."
$asJob = Start-Job -ScriptBlock {
  param($u, $h, $s)
  ssh "$u@$h" "cd $s && chmod +x *.sh && ./04-run-role.sh as"
} -ArgumentList $asUser, $asHost, $remoteScripts

Start-Sleep -Seconds 2   # give AS a moment to bind its socket

# Step 2: Start Device Node on RPi #2 (background SSH)
Write-Host "[orchestrate] Starting Device Node on $nodeHost ..."
$nodeJob = Start-Job -ScriptBlock {
  param($u, $h, $s)
  ssh "$u@$h" "cd $s && chmod +x *.sh && ./04-run-role.sh node"
} -ArgumentList $nodeUser, $nodeHost, $remoteScripts

Write-Host ""
Write-Host "[orchestrate] Now start the GW on this laptop:"
Write-Host "  bash .\scripts\04-run-role.sh gw"
Write-Host ""
Write-Host "Press Ctrl-C to stop monitoring when done."

# Stream output from both jobs until user interrupts
try {
  while ($true) {
    Receive-Job -Job $asJob   | ForEach-Object { Write-Host "[AS]   $_" }
    Receive-Job -Job $nodeJob | ForEach-Object { Write-Host "[NODE] $_" }
    Start-Sleep -Milliseconds 500
  }
} finally {
  Stop-Job  -Job $asJob, $nodeJob
  Remove-Job -Job $asJob, $nodeJob -Force
}
