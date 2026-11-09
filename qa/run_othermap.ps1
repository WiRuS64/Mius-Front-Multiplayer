# "Next turn" on an operation other than the one run_operation.ps1 plays: picks the operation at -Op (fractions of the
# game window, on the Operations screen), both players press next turn with no orders given, the turn must be carried out.
#   run_othermap.ps1 -Op "0.584,0.632" [-Tag othermap]
param([string]$Game = "$env:USERPROFILE\Desktop\миус тесты", [string]$Tag = "othermap", [string]$Op = "0.584,0.632", [string]$StartOp = "0.5845,0.9067")
$ErrorActionPreference = "Continue"
$Game = (Resolve-Path $Game).Path
$env:MP_QA_OP = $Op
$env:MP_QA_STARTOP = $StartOp
$setup = & powershell -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\run_operation.ps1" -Game $Game -Tag "$Tag-setup" -StopBeforeOrder 2>&1
$env:MP_QA_OP = $null; $env:MP_QA_STARTOP = $null
$setup | Select-Object -Last 14
. "$Game\_mp_research\tools\auto.ps1"
$script:Game = $Game
$runDir = "$PSScriptRoot\runs\$Tag-$(Get-Date -Format yyyyMMdd-HHmmss)"
New-Item -ItemType Directory -Force $runDir | Out-Null
$script:Shots = $runDir
Start-Transcript -Path "$runDir\transcript.txt" | Out-Null
$mine = New-Object System.Collections.ArrayList
function Done {
    foreach ($g in @($mine)) { Stop-Game $g }
    Start-Sleep 2
    # the map processes a turn starts are this run's too: only ones in this test folder
    Get-CimInstance Win32_Process -Filter "Name='starter_x64.exe'" | Where-Object { $_.ExecutablePath -like "$Game\*" } | ForEach-Object { Stop-Game (Get-Process -Id $_.ProcessId) }
    Get-ChildItem "$Game\mp_logs" -Filter "basic_network*.log" | Copy-Item -Destination $runDir
    Show-Results
    $fail = @($script:Results | Where-Object Result -eq FAIL).Count
    "RESULT: $(if ($fail -eq 0) { 'PASS' } else { 'FAIL' })  ($runDir)"
    Stop-Transcript | Out-Null
    exit $(if ($fail -eq 0) { 0 } else { 1 })
}
$pidline = ($setup | Select-String 'P1 (\d+), P2 map (\d+)' | Select-Object -Last 1)
Check "setup: both games on their maps" ([bool]$pidline) $(if ($pidline) { $pidline.Line })
if (-not $pidline) { Done }
$p1 = Get-Process -Id ([int]$pidline.Matches[0].Groups[1].Value)
$p2 = Get-Process -Id ([int]$pidline.Matches[0].Groups[2].Value)
[void]$mine.Add($p1); [void]$mine.Add($p2)
$p1log = Get-MpLog $p1 "opgame"; $p2log = Get-MpLog $p2 "opgame"
$shared = Select-String -Path $p1log -Pattern 'map: shared with' | Select-Object -Last 1
Check "the map was shared" ([bool]$shared) $(if ($shared) { $shared.Line.Substring(22) })
[void](Save-Shot $p2 "p2_map")
Send-Command $p2 "endturn"
Check "P2 pressed next turn" ([bool](Wait-Log $p2log 'this player has ended the turn' 10))
Start-Sleep 4
Send-Command $p1 "endturn"
Check "P1 pressed next turn, P2's moves asked for" ([bool](Wait-Log $p1log 'asking .* for his moves' 15))
Check "P1 received P2's map" ([bool](Wait-Log $p1log "the other player's map received" 90))
$line = Wait-Log $p1log 'moves are in' 30
Check "P2's moves merged" ([bool]$line) $(if ($line) { $line.Substring(22) })
$gave = Select-String -Path $p1log -Pattern 'did not arrive' -Quiet
Check "the watchdog did not fire" (-not $gave)
$deadline = (Get-Date).AddSeconds(150); $turn = $null
while (-not $turn -and (Get-Date) -lt $deadline) {
    $turn = Get-ChildItem "$Game\mp_logs" -Filter "basic_network_opgame*.log" | Where-Object { $_.LastWriteTime -gt (Get-Date).AddMinutes(-4) } | Select-String -Pattern 'turn processed with both players' | Select-Object -Last 1
    if (-not $turn) { Start-Sleep 2 }
}
Check "turn carried out with both players' moves" ([bool]$turn) $(if ($turn) { $turn.Line.Substring(22) })
Done
