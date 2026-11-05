# Operation test, two games on one PC, the whole round a player sees (based on MiusPlayer tools\test_opmap.ps1,
# which needs a ready operation save; this one starts a NEW operation through the menus):
#   P1: MULTIPLAYER -> HOST AN OPERATION -> CHOOSE THE OPERATION -> Stepanovka 30-31 Oct 1941, Soviet side ->
#       "start operation" -> closes the briefing (the map has to be on screen for it to be shared)
#   P2: MULTIPLAYER -> JOIN A GAME 127.0.0.1 -> READY; the host's game shares its map, P2's game opens the German
#       side of the same operation; P2 orders one battle group to move (left click on it, right click on a square)
#   both press next turn: P2's moves go to the host, are merged, the turn is carried out
#   P1 starts the battle P2's move led to; P2's game enters it from the map; both press Start twice; units compared
#   P1 leaves the battle; P1 back on the map, P2 back in P1's lobby by itself
#   P1 presses next turn twice (battle results, then the turn): turn 2's map goes to P2, P2 on its map again
# Click spots are fractions of a 16:9 game window, taken from screenshots of this operation's first turn.
#   run_operation.ps1 [-Tag op] [-Fight 60] [-KeepRunning]
param([Parameter(Mandatory=$true)][string]$Game, [string]$Tag = "operation", [int]$Fight = 60, [switch]$KeepRunning,
      [double[]]$Op = @(0.584, 0.347), [double[]]$StartOp = @(0.5836, 0.6222), [double[]]$Group = @(0.1484, 0.4806),
      [double[]]$Square = @(0.1670, 0.4531), [double[]]$Zone = @(0.1758, 0.4694), [switch]$StopBeforeOrder, [int]$MaxTurns = 4)
$ErrorActionPreference = "Continue"
$Game = (Resolve-Path $Game).Path
$Py = if ($env:MP_PYTHON) { $env:MP_PYTHON } else { "python" }   # set MP_PYTHON to use another Python 3
. "$Game\_mp_research\tools\auto.ps1"
$script:Game = $Game
$tools = "$Game\_mp_research\tools"
$runDir = "$PSScriptRoot\runs\$Tag-$(Get-Date -Format yyyyMMdd-HHmmss)"
New-Item -ItemType Directory -Force $runDir | Out-Null
$script:Shots = $runDir
Start-Transcript -Path "$runDir\transcript.txt" | Out-Null
if (Get-Process starter_x64 -ErrorAction SilentlyContinue) { "A game instance is already running; not touching it. RESULT: SKIP"; Stop-Transcript | Out-Null; exit 2 }
Get-ChildItem "$Game\out" -Filter "basic_network*.log" -ErrorAction SilentlyContinue | ForEach-Object { [IO.File]::Delete($_.FullName) }
# a new operation each time: the test copy's saves of this operation are moved into the run folder
$prof = "$Game\users\profiles\cloud"
Get-ChildItem $prof -Filter "1941_10_Mius_30_10_stepanovka_*" -ErrorAction SilentlyContinue | Move-Item -Destination $runDir -Force
$started = Get-Date
$dumpBefore = Get-Item "$Game\out\minidump.dmp" -ErrorAction SilentlyContinue

function Programs([string]$kind, [int[]]$except) {
    Get-CimInstance Win32_Process -Filter "Name='starter_x64.exe'" | Where-Object {
        $tac = $_.CommandLine -match 'tacgame\.progpack'; $op = $_.CommandLine -match 'opgame\.progpack'
        $except -notcontains $_.ProcessId -and (($kind -eq 'battle' -and $tac) -or ($kind -eq 'map' -and $op) -or ($kind -eq 'menu' -and -not $tac -and -not $op))
    } | ForEach-Object { Get-Process -Id $_.ProcessId }
}
function Wait-Program([string]$kind, [int[]]$except, [int]$timeout = 60) {
    for ($i = 0; $i -lt $timeout; $i++) { $p = Programs $kind $except | Select-Object -First 1; if ($p) { return $p }; Start-Sleep 1 }
    $null
}
function Orders($proc) {
    $log = Get-MpLog $proc "opgame"
    $before = @(Select-String -Path $log -Pattern 'test: operation saved').Count
    Send-Command $proc "savemap"
    for ($i = 0; $i -lt 20; $i++) {
        $m = @(Select-String -Path $log -Pattern 'test: operation saved .*turn phase (\d+), (\d+) orders')
        if ($m.Count -gt $before) { return [pscustomobject]@{ Phase = [int]$m[-1].Matches[0].Groups[1].Value; Orders = [int]$m[-1].Matches[0].Groups[2].Value } }
        Start-Sleep -Milliseconds 500
    }
    $null
}
function Right-Click($proc, [double]$fx, [double]$fy) {
    # no Focus-Game here: the window is in front from the click that selected the group, and bringing it to the
    # front again drops the selection
    $r = New-Object GtAuto+RECT; [void][GtAuto]::GetWindowRect($proc.MainWindowHandle, [ref]$r)
    [void][GtAuto]::SetCursorPos([int]($r.L + ($r.R - $r.L) * $fx), [int]($r.T + ($r.B - $r.T) * $fy)); Start-Sleep -Milliseconds 250
    [GtAuto]::mouse_event(1, 2, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 120
    [GtAuto]::mouse_event(1, -2, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 120
    [GtAuto]::mouse_event(8, 0, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 120
    [GtAuto]::mouse_event(16, 0, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 300
}
function Away { [void][GtAuto]::SetCursorPos(40, 1400) }
function Finish {
    $d = Get-Item "$Game\out\minidump.dmp" -ErrorAction SilentlyContinue
    Check "no crash dump" (-not ($d -and (-not $dumpBefore -or $d.LastWriteTime -gt $started)))
    Get-WinEvent -FilterHashtable @{ LogName = 'Application'; Id = 1000; StartTime = $started } -ErrorAction SilentlyContinue |
        Where-Object { $_.Message -match 'starter_x64' } | ForEach-Object { Check "no Windows crash event" $false (($_.Message -split "`n")[0..6] -join ' ') }
    if (-not $KeepRunning) { foreach ($g in @(Get-Process starter_x64 -ErrorAction SilentlyContinue)) { Stop-Game $g } }
    Get-ChildItem "$Game\out" -Filter "basic_network*.log" | Copy-Item -Destination $runDir
    Show-Results
    $fail = @($script:Results | Where-Object Result -eq FAIL).Count
    "RESULT: $(if ($fail -eq 0) { 'PASS' } else { 'FAIL' })  ($runDir)"
    Stop-Transcript | Out-Null
    exit $(if ($fail -eq 0) { 0 } else { 1 })
}

# ---- P1: host an operation through the menus, start a new one, close its briefing
$p1 = Start-Game "" @{}
$p1log = Get-MpLog $p1 "opgame"
[void](Wait-Log $p1log 'render pipeline reached' 60); Start-Sleep 6
[void](Click-Game $p1 0.5 0.129); Start-Sleep -Milliseconds 800
[void](Click-Game $p1 0.56 0.517)
Check "P1: hosting an operation" ([bool](Wait-Log $p1log 'hosting operation chosen' 8))
Start-Sleep 1
[void](Click-Game $p1 0.56 0.683)
Check "P1: Operations screen open" ([bool](Wait-Log $p1log 'opened the stock campaign screen' 8))
Away; Start-Sleep 3
[void](Click-Game $p1 $Op[0] $Op[1]); Away; Start-Sleep 3
[void](Save-Shot $p1 "p1_conditions")
[void](Click-Game $p1 $StartOp[0] $StartOp[1]); Away
$p1op = $null
for ($i = 0; $i -lt 60 -and -not $p1op; $i++) { Start-Sleep 1; $o = Orders $p1; if ($o) { $p1op = $o } }
Check "P1: new operation open on its map" ([bool]$p1op) $(if ($p1op) { "turn phase $($p1op.Phase)" })
if (-not $p1op) { [void](Save-Shot $p1 "p1_no_operation"); Finish }
Press-Key $p1 0x71; Away; Start-Sleep 2      # F2: briefing off
[void](Save-Shot $p1 "p1_map")

# ---- P2: join, ready; the map comes by itself
$p2 = Start-Game "" @{}
$p2log = Get-MpLog $p2 "opgame"
[void](Wait-Log $p2log 'render pipeline reached' 60); Start-Sleep 6
[void](Click-Game $p2 0.5 0.129); Start-Sleep -Milliseconds 800
[void](Click-Game $p2 0.56 0.609)
Start-Sleep -Milliseconds 600; Press-Key $p2 0x2E; Type-Text $p2 "127.0.0.1"; Start-Sleep -Milliseconds 400
[void](Click-Game $p2 0.56 0.424)
Check "P2: in P1's lobby" ([bool](Wait-Log $p1log 'net: player connected' 20))
Start-Sleep 2
[void](Click-Game $p2 0.56 0.591)
Check "P2: ready" ([bool](Wait-Log $p2log 'lobby: ready' 8))
$line = Wait-Log $p1log 'map: shared with' 60
Check "P1: map shared with P2" ([bool]$line) $(if ($line) { $line.Substring(22) })
$p2map = Wait-Program 'map' @($p1.Id) 90
Check "P2: operation program started" ([bool]$p2map)
if (-not $p2map) { Finish }
$cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($p2map.Id)").CommandLine
Check "P2: plays the other side (stepanovka_ger)" ($cmd -match 'stepanovka_ger') ($cmd.Substring($cmd.IndexOf('opgame')))
$p2maplog = Get-MpLog $p2map "opgame"
Check "P2: its side of the map" ([bool](Wait-Log $p2maplog "this player's side of the operational map" 90))
Check "P2: connected to P1 from the map" ([bool](Wait-Log $p2maplog 'net: connected to host' 60))
$line = Wait-Log $p2maplog "own scouting worked out" 30
Check "P2: fog of war over P1's groups (few seen)" ($line -match 'groups (\d+) seen' -and [int]$Matches[1] -lt 20) $(if ($line) { $line.Substring(22) })
Start-Sleep 8
[void][GtAuto]::SetCursorPos(40, 700); Click-Game $p2map (12 / 1280) (349 / 720) | Out-Null; Away; Start-Sleep 2   # briefing off
[void](Save-Shot $p2map "p2_map")

# ---- turns: P2 orders its battle group one step east, both press next turn, the turn is carried out. A turn that
#      leads to a new orders phase sends P2 the next map (checked); one that leads to a battle ends the loop. Whether
#      contact happens in a given turn depends on the computer's moves, so up to $MaxTurns turns are played.
if ($StopBeforeOrder) { "P1 $($p1.Id), P2 map $($p2map.Id)"; Stop-Transcript | Out-Null; exit 0 }
$seen = New-Object System.Collections.ArrayList; [void]$seen.Add($p1.Id); [void]$seen.Add($p2.Id); [void]$seen.Add($p2map.Id)
$hostMap = $p1; $hostLog = $p1log
$g = $Group; $s = $Square
$bt = $null
for ($turn = 1; $turn -le $MaxTurns -and -not $bt; $turn++) {
    "--- turn $turn"
    $o = Orders $p2map
    $o2 = $o
    for ($try = 0; $try -lt 4 -and $o2 -and $o2.Orders -le $o.Orders; $try++) {
        if ($try -gt 0) { [void](Click-Game $p2map (12 / 1280) (349 / 720)); Away; Start-Sleep 2 }   # the briefing layer was still up: toggle it
        [void](Click-Game $p2map 0.742 0.944); Start-Sleep 1     # the first click after the window comes to the front is not taken as a selection
        [void](Click-Game $p2map $g[0] $g[1]); Start-Sleep 1
        Right-Click $p2map $s[0] $s[1]; Start-Sleep 2; Away
        $o2 = Orders $p2map
        "order try $($try + 1): $($o2.Orders) orders"
    }
    [void](Save-Shot $p2map "p2_ordered_turn$turn")
    Check "turn ${turn}: P2 gave an order (counted in its own save)" ($o2 -and $o2.Orders -gt $o.Orders) "$($o.Orders) -> $($o2.Orders) orders"

    Send-Command $p2map "endturn"
    Check "turn ${turn}: P2 pressed next turn, waits for P1" ([bool](Wait-Log $p2maplog 'this player has ended the turn, waiting' 10))
    Start-Sleep 6
    Check "turn ${turn}: the turn does not end on P2's press alone" (-not (Select-String -Path $hostLog -Pattern 'asking .* for his moves|map: ending the turn' -Quiet))
    Send-Command $hostMap "endturn"
    Check "turn ${turn}: P1 pressed next turn, P2's moves asked for" ([bool](Wait-Log $hostLog 'asking .* for his moves' 15))
    Check "turn ${turn}: P1 received P2's map" ([bool](Wait-Log $hostLog "the other player's map received" 60))
    $line = Wait-Log $hostLog 'moves are in' 20
    $merged = if ($line -match '\((\d+) orders') { [int]$Matches[1] } else { -1 }
    Check "turn ${turn}: P2's order merged into the operation" ($merged -ge 1) $(if ($line) { $line.Substring(22) })
    $p1b = Wait-Program 'map' @($seen) 60
    Check "turn ${turn}: P1 restarted on the merged save" ([bool]$p1b)
    if (-not $p1b) { Finish }
    [void]$seen.Add($p1b.Id)
    $line = Wait-Log (Get-MpLog $p1b "opgame") 'turn processed with both players' 90
    Check "turn ${turn}: carried out with both players' moves" ([bool]$line) $(if ($line) { $line.Substring(22) })
    $p1c = Wait-Program 'map' @($seen) 60
    Check "turn ${turn}: P1 map reloaded after the turn" ([bool]$p1c)
    if (-not $p1c) { Finish }
    [void]$seen.Add($p1c.Id)
    $hostMap = $p1c; $hostLog = Get-MpLog $p1c "opgame"
    Check "turn ${turn}: P1 hosting again" ([bool](Wait-Log $hostLog 'net: hosting on' 90))
    Start-Sleep 12; Away
    [void](Save-Shot $p1c "p1_after_turn$turn")
    $shared = Wait-Log $hostLog 'map: shared with' 10
    if ($shared) {
        # no battle: the next turn's orders phase; P2's map reloads
        Check "turn ${turn}: no battle - next turn's map shared with P2" $true $shared.Substring(22)
        Check "turn ${turn}: P2 told the new turn has arrived" ([bool](Wait-Log $p2maplog 'offers the map of the next turn|the new turn has arrived' 40))
        $p2n = Wait-Program 'map' @($seen) 90
        Check "turn ${turn}: P2 on its map for the next turn" ([bool]$p2n)
        if (-not $p2n) { Finish }
        [void]$seen.Add($p2n.Id)
        $p2map = $p2n; $p2maplog = Get-MpLog $p2n "opgame"
        Check "turn ${turn}: P2 connected again" ([bool](Wait-Log $p2maplog 'net: connected to host' 60))
        Start-Sleep 10
        [void](Click-Game $p2map (12 / 1280) (349 / 720)); Away; Start-Sleep 2
        $g = $s; $s = @(($s[0] + 0.0176), $s[1])
        continue
    }
    # a battle is pending where P2's group went: P1 starts it from the map
    [void](Click-Game $p1c ($s[0] + 0.008) ($s[1] + 0.016)); Away
    $bt = Wait-Program 'battle' @() 90
    Check "turn ${turn}: P1 started the battle from the map" ([bool]$bt)
    if (-not $bt) { Finish }
}
if (-not $bt) { Check "a battle came about within $MaxTurns turns" $false; Finish }
$btlog = Get-MpLog $bt "tacgame"
Check "P1: battle hosted" ([bool](Wait-Log $btlog 'net: hosting battle on' 180))
$bt2 = Wait-Program 'battle' @($bt.Id) 180
Check "P2: entered the battle from its map" ([bool]$bt2)
if (-not $bt2) { Finish }
$bt2log = Get-MpLog $bt2 "tacgame"
Check "P2: connected inside the battle" ([bool](Wait-Log $bt2log 'net: connected to host' 180))
$l1 = Wait-Log $btlog 'this player commands' 5; $l2 = Wait-Log $bt2log 'this player commands' 5
Check "sides: P1 Soviets, P2 Germans" ($l1 -match 'commands Soviets' -and $l2 -match 'commands Germans') "$(if ($l1) { $l1.Substring(22) }) / $(if ($l2) { $l2.Substring(22) })"
Start-Sleep 20
Send-Ready $bt; Send-Ready $bt2
Check "deployment ended in both games" ([bool](Wait-Log $btlog 'phase: initial orders' 40) -and [bool](Wait-Log $bt2log 'phase: initial orders' 40))
Start-Sleep 4
Send-Ready $bt; Send-Ready $bt2
Check "the battle began in both games" ([bool](Wait-Log $btlog 'phase: battle$' 40) -and [bool](Wait-Log $bt2log 'phase: battle$' 40))
Start-Sleep $Fight
$diff = & $Py "$tools\combat_diff.py" $bt.Id $bt2.Id 4 15 2>&1
$diff | Where-Object { $_ -match 'sample|disagree|worst|Traceback|Error' }
$worst = if (($diff | Out-String) -match 'worst sample: (\d+)') { [int]$Matches[1] } else { 999 }
$far = @($diff | Select-String 'more than 5 m apart: (\d+)' | ForEach-Object { [int]$_.Matches[0].Groups[1].Value })
Check "operation battle: units agree (at most 5 disagreeing)" ($worst -le 5) "worst sample: $worst"
Check "operation battle: no unit more than 5 m apart in the last sample" ($far.Count -gt 0 -and $far[-1] -eq 0) "all samples: $($far -join ' ')"
foreach ($pair in @(@("P1", $btlog), @("P2", $bt2log))) {
    $m = Select-String -Path $pair[1] -Pattern 'net: 5 s: .*largest ([0-9.]+) m, (\d+) jumps' | Select-Object -Last 1
    Check "$($pair[0]): position corrections small (largest under 1 m, no jumps)" ($m -and [double]$m.Matches[0].Groups[1].Value -lt 1 -and [int]$m.Matches[0].Groups[2].Value -eq 0) $(if ($m) { $m.Line.Substring(22) })
}

# ---- P1 leaves the battle; both go back
Send-Resign $bt
for ($i = 0; $i -lt 90 -and -not $bt.HasExited; $i++) { Start-Sleep 1; $bt.Refresh() }
Check "P1: battle program ended" $bt.HasExited
for ($i = 0; $i -lt 60 -and -not $bt2.HasExited; $i++) { Start-Sleep 1; $bt2.Refresh() }
Check "P2: battle program ended" $bt2.HasExited
$p1d = Wait-Program 'map' @($seen) 90
Check "P1: back on the operational map" ([bool]$p1d)
$p2m = Wait-Program 'menu' @($p1.Id, $p2.Id) 60
Check "P2: back in P1's lobby by itself" ([bool]$p2m -and [bool](Wait-Log (Get-MpLog $p2m "opgame") 'rejoining the lobby' 90))
if (-not $p1d -or -not $p2m) { Finish }
$p1dlog = Get-MpLog $p1d "opgame"
[void](Wait-Log $p1dlog 'net: hosting on' 60); Start-Sleep 10

# ---- next turn: battle results, then the turn; turn 2's map goes to P2
Send-Command $p1d "endturn"; Start-Sleep 20
$shared = Wait-Log $p1dlog 'map: shared with' 5
if (-not $shared) { Send-Command $p1d "endturn"; $shared = Wait-Log $p1dlog 'map: shared with' 60 }
Check "P1: turn 2's map shared with P2" ([bool]$shared) $(if ($shared) { $shared.Substring(22) })
$p2n = Wait-Program 'map' @($seen + @($p1d.Id)) 90
Check "P2: on its map for turn 2" ([bool]$p2n)
if ($p2n) {
    $p2nlog = Get-MpLog $p2n "opgame"
    Check "P2: connected to P1 for turn 2" ([bool](Wait-Log $p2nlog 'net: connected to host' 60))
    Start-Sleep 12; Away; [void](Save-Shot $p2n "p2_turn2")
}
Finish