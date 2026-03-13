Param(
  [string]$RolesFile = "$PSScriptRoot\..\config\roles.env"
)

if (-not (Test-Path $RolesFile)) {
  Write-Error "roles.env not found: $RolesFile"
  exit 1
}

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

$asUser = $map["AS_USER"]
$asHost = $map["AS_HOST"]
$nodeUser = $map["NODE_USER"]
$nodeHost = $map["NODE_HOST"]
$remoteBase = $map["REMOTE_BASE_DIR"]
$projectDir = $map["PROJECT_DIR_NAME"]

if (-not $asHost -or -not $nodeHost) {
  Write-Error "Missing AS_HOST or NODE_HOST in roles.env"
  exit 1
}

if (-not $asUser) { $asUser = "pi" }
if (-not $nodeUser) { $nodeUser = "pi" }

$remoteScripts = "$remoteBase/$projectDir/scripts"

Write-Host "[orchestrate] Starting AS on $asHost"
ssh "$asUser@$asHost" "cd $remoteScripts && chmod +x *.sh && ./04-run-role.sh as"

Write-Host "[orchestrate] Starting Node on $nodeHost"
ssh "$nodeUser@$nodeHost" "cd $remoteScripts && chmod +x *.sh && ./04-run-role.sh node"

Write-Host "[orchestrate] Run GW locally on laptop"
Write-Host "bash ./scripts/04-run-role.sh gw"
