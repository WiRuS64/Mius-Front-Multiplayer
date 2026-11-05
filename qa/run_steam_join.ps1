# Joining through Steam, two games on one PC. Two real Steam accounts on two PCs are needed for the real thing; here
# the mod's own test stand-in for Steam's peer-to-peer networking is used (MP_STEAM_FAKE=<id>: the game is
# "steam:<id>" and its Steam datagrams travel over UDP on this PC). Everything above the transport is the real
# code path: the Join Game text Steam passes on the command line (+gtmf_join=steam:<id>), the lobby, the battle
# download over Steam, the battle itself over Steam.
#   A hosts the saved test battle (MP_ROLE=host) as steam:<HostId>
#   B starts the way Steam's "Join Game" starts it: opgame.progpack, +gtmf_join=steam:<HostId>; B is ready in the lobby
#   B's game downloads the battle and enters it; both press Start twice; units compared
# Also checks, against the real Steam client on this PC: Steam is running for the game, the note for friends is taken.
#   run_steam_join.ps1 [-Tag steam] [-HostId 7101] [-JoinId 7102]
#   The stand-in binds UDP port id + 40000 (mod rva 0x3f832) and takes the sender id from the port, so ids must stay under 25536.
param([Parameter(Mandatory=$true)][string]$Game, [string]$Tag = "steam", [ValidateRange(1, 25535)][int]$HostId = 7101, [ValidateRange(1, 25535)][int]$JoinId = 7102,
      [int]$Warmup = 40, [switch]$KeepRunning)
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
Copy-Item "$Game\_mp_research\test_battle_image.cfgpack" "$Game\data\common\shared\config\tacgame_image.cfgpack" -Force
$started = Get-Date
$dumpBefore = Get-Item "$Game\out\minidump.dmp" -ErrorAction SilentlyContinue
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$half = [int]($screen.Width / 2)

function Battles([int[]]$except) {
    Get-CimInstance Win32_Process -Filter "Name='starter_x64.exe'" |
        Where-Object { $_.CommandLine -match 'tacgame\.progpack' -and $except -notcontains $_.ProcessId } | ForEach-Object { Get-Process -Id $_.ProcessId }
}
function Finish {
    $d = Get-Item "$Game\out\minidump.dmp" -ErrorAction SilentlyContinue
    Check "no crash dump" (-not ($d -and (-not $dumpBefore -or $d.LastWriteTime -gt $started)))
    if (-not $KeepRunning) { foreach ($g in @(Get-Process starter_x64 -ErrorAction SilentlyContinue)) { Stop-Game $g } }
    Get-ChildItem "$Game\out" -Filter "basic_network*.log" | Copy-Item -Destination $runDir
    Show-Results
    $fail = @($script:Results | Where-Object Result -eq FAIL).Count
    "RESULT: $(if ($fail -eq 0) { 'PASS' } else { 'FAIL' })  ($runDir)"
    Stop-Transcript | Out-Null
    exit $(if ($fail -eq 0) { 0 } else { 1 })
}

# ---- A: host, Steam stand-in
$a = Start-Game "root\programs\tacgame.progpack, data\common\shared\config\tacgame_image.cfgpack, users\profiles, cloud, *:*, 0, 1" @{
    MP_ROLE = "host"; MP_STEAM_FAKE = "$HostId"; MP_WINDOW = "0,0,$half,$($screen.Height)" }
$alog = Get-MpLog $a "tacgame"
Check "A: hosting the battle" ([bool](Wait-Log $alog 'net: hosting battle on' 120))
$line = Wait-Log $alog 'steam: TEST STAND-IN' 10
Check "A: Steam stand-in active (steam:$HostId)" ([bool]$line) $(if ($line) { $line.Substring(22) })

# ---- B: started as Steam's Join Game starts it
$b = Start-Game "root\programs\opgame.progpack, +gtmf_join=steam:$HostId" @{ MP_STEAM_FAKE = "$JoinId"; MP_WINDOW = "$half,0,$half,$($screen.Height)" }
$blog = Get-MpLog $b "opgame"
$line = Wait-Log $blog "Steam's Join Game asks to join|joining .* through Steam" 90
Check "B: takes Steam's Join Game text" ([bool]$line) $(if ($line) { $line.Substring(22) })
$line = Wait-Log $alog 'player connected through Steam' 90
Check "A: B connected through Steam" ([bool]$line) $(if ($line) { $line.Substring(22) })
Start-Sleep 3
[void](Save-Shot $b "b_lobby")
[void](Click-Game $b 0.75 0.97)             # wake: the first click after focusing is swallowed
[void](Click-Game $b 0.425 0.594)           # READY (the skirmish lobby has SWAP SIDES to its right)
Check "B: ready in A's lobby" ([bool](Wait-Log $blog 'lobby: ready' 10))
Check "B: battle downloaded through Steam" ([bool](Wait-Log $blog 'battle received|Battle received' 120))
$bt = $null; for ($i = 0; $i -lt 90 -and -not $bt; $i++) { $bt = Battles @($a.Id) | Select-Object -First 1; if (-not $bt) { Start-Sleep 1 } }
Check "B: battle started" ([bool]$bt)
if (-not $bt) { [void](Save-Shot $b "b_no_battle"); Finish }
$btlog = Get-MpLog $bt "tacgame"
$line = Wait-Log $btlog 'net: joining through Steam|net: connected to host' 120
Check "B (battle): joins the host through Steam" ((Select-String -Path $btlog -Pattern 'joining through Steam' -Quiet)) $(if ($line) { $line.Substring(22) })
Check "B (battle): connected to A" ([bool](Wait-Log $btlog 'net: connected to host' 120))
$l = Wait-Log $btlog 'this player commands' 10
Check "B: commands the Germans" ($l -match 'commands Germans') $(if ($l) { $l.Substring(22) })
Check "Start button shared (A)" ([bool](Wait-Log $alog 'Start button shared' 30))
Start-Sleep 5
Send-Ready $a; Send-Ready $bt
Check "deployment ended in both games" ([bool](Wait-Log $alog 'phase: initial orders' 40) -and [bool](Wait-Log $btlog 'phase: initial orders' 40))
Start-Sleep 3
Send-Ready $a; Send-Ready $bt
Check "the battle began in both games" ([bool](Wait-Log $alog 'phase: battle$' 40) -and [bool](Wait-Log $btlog 'phase: battle$' 40))
Start-Sleep $Warmup
$diff = & $Py "$tools\combat_diff.py" $a.Id $bt.Id 3 15 2>&1
$diff | Where-Object { $_ -match 'sample|disagree|worst|Traceback|Error' }
$worst = if (($diff | Out-String) -match 'worst sample: (\d+)') { [int]$Matches[1] } else { 999 }
$far = @($diff | Select-String 'more than 5 m apart: (\d+)' | ForEach-Object { [int]$_.Matches[0].Groups[1].Value })
Check "units agree (at most 5 disagreeing)" ($worst -le 5) "worst sample: $worst"
Check "no unit more than 5 m apart in the last sample" ($far.Count -gt 0 -and $far[-1] -eq 0) "all samples: $($far -join ' ')"
$m = Select-String -Path $btlog -Pattern 'steam: 5 s: (\d+) datagrams sent through Steam, (\d+) received' | Select-Object -Last 1
Check "B: battle traffic goes through Steam" ($m -and [int]$m.Matches[0].Groups[1].Value -gt 0 -and [int]$m.Matches[0].Groups[2].Value -gt 0) $(if ($m) { $m.Line.Substring(22) })
foreach ($pair in @(@("A", $alog), @("B", $btlog))) {
    $m = Select-String -Path $pair[1] -Pattern 'net: 5 s: .*largest ([0-9.]+) m, (\d+) jumps' | Select-Object -Last 1
    Check "$($pair[0]): position corrections small" ($m -and [double]$m.Matches[0].Groups[1].Value -lt 1 -and [int]$m.Matches[0].Groups[2].Value -eq 0) $(if ($m) { $m.Line.Substring(22) })
}
$a.Refresh(); $bt.Refresh()
Check "both still running" (-not $a.HasExited -and -not $bt.HasExited)
Finish
