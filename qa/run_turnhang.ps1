# The turn must not hang when the joining player is not on his map at the moment the host collects the moves.
# Sets up a two-game operation with run_operation.ps1 -StopBeforeOrder, then: P2 presses next turn and leaves its map
# (Esc), P1 presses next turn. Expected with the watchdog (2.6.0): P1 gives up within the limit and says so. On 2.5.0 the host waits for ever.
#   run_turnhang.ps1 [-Tag hang] [-Wait 70]
param([string]$Game = "$env:USERPROFILE\Desktop\миус тесты", [string]$Tag = "hang", [int]$Wait = 70)
$ErrorActionPreference = "Continue"
$Game = (Resolve-Path $Game).Path
$setup = & powershell -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\run_operation.ps1" -Game $Game -Tag "$Tag-setup" -StopBeforeOrder 2>&1
$setup | Select-Object -Last 4
. "$Game\_mp_research\tools\auto.ps1"
$script:Game = $Game
$runDir = "$PSScriptRoot\runs\$Tag-$(Get-Date -Format yyyyMMdd-HHmmss)"
New-Item -ItemType Directory -Force $runDir | Out-Null
$script:Shots = $runDir
Start-Transcript -Path "$runDir\transcript.txt" | Out-Null
$pidline = ($setup | Select-String 'P1 (\d+), P2 map (\d+)' | Select-Object -Last 1)
Check "setup: both games on their maps" ([bool]$pidline) $(if ($pidline) { $pidline.Line })
function Done {
    Get-CimInstance Win32_Process -Filter "Name='starter_x64.exe'" | Where-Object { $_.ExecutablePath -like "$Game\*" } | ForEach-Object { Stop-Game (Get-Process -Id $_.ProcessId) }
    Get-ChildItem "$Game\mp_logs" -Filter "basic_network*.log" | Copy-Item -Destination $runDir
    Show-Results
    $fail = @($script:Results | Where-Object Result -eq FAIL).Count
    "RESULT: $(if ($fail -eq 0) { 'PASS' } else { 'FAIL' })  ($runDir)"
    Stop-Transcript | Out-Null
    exit $(if ($fail -eq 0) { 0 } else { 1 })
}
if (-not $pidline) { Done }
$p1 = Get-Process -Id ([int]$pidline.Matches[0].Groups[1].Value)
$p2 = Get-Process -Id ([int]$pidline.Matches[0].Groups[2].Value)
$p1log = Get-MpLog $p1 "opgame"; $p2log = Get-MpLog $p2 "opgame"
Send-Command $p2 "endturn"
Check "P2 pressed next turn" ([bool](Wait-Log $p2log 'this player has ended the turn' 8))
Press-Key $p2 0x1B                          # Esc: leaves the map for the Operations screen
Start-Sleep -Milliseconds 300
Send-Command $p1 "endturn"
Check "P1 pressed next turn, P2's moves asked for" ([bool](Wait-Log $p1log 'asking .* for his moves' 15))
$line = Wait-Log $p1log 'did not arrive' $Wait
Check "P1 gave up on the moves by itself (no endless wait)" ([bool]$line) $(if ($line) { $line.Substring(22) })
$sending = Select-String -Path $p1log -Pattern 'is sending his moves' -Quiet
"P2 sent its moves anyway: $sending"
[void](Save-Shot $p1 "p1_after_giveup")
$p1.Refresh()
Check "P1 still running" (-not $p1.HasExited)
Select-String -Path $p2log -Pattern 'map: |lobby' | Select-Object -Last 8 | ForEach-Object { $_.Line.Substring(13, [Math]::Min(150, $_.Line.Length - 13)) }
Select-String -Path $p1log -Pattern 'map: |net: player' | Select-Object -Last 8 | ForEach-Object { $_.Line.Substring(13, [Math]::Min(150, $_.Line.Length - 13)) }
Done
