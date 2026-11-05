# Two-player battle test on one PC, no mouse or keyboard input (based on MiusPlayer tools\test_versus.ps1).
# Game A hosts the saved test battle (MP_ROLE=host), game B joins through mp_join.exe; both press Start through
# the mod's MP_TEST command file. Checks phases, the shared Start button, unit agreement, fog of war, crashes.
#   run_versus.ps1 -Tag baseline [-Side germans|soviets] [-Warmup 60] [-Samples 6] [-Every 20] [-KeepRunning]
param([Parameter(Mandatory=$true)][string]$Game, [string]$Tag = "run", [ValidateSet("germans", "soviets")][string]$Side = "germans",
      [int]$Warmup = 60, [int]$Samples = 6, [int]$Every = 20, [switch]$KeepRunning, [hashtable]$Extra = @{})
$ErrorActionPreference = "Continue"
$Game = (Resolve-Path $Game).Path
$Py = "D:\programs\Python312\python.exe"
. "$Game\_mp_research\tools\auto.ps1"
$script:Game = $Game
$tools = "$Game\_mp_research\tools"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = "$PSScriptRoot\runs\$Tag-$stamp"
New-Item -ItemType Directory -Force $runDir | Out-Null
$script:Shots = $runDir
Start-Transcript -Path "$runDir\transcript.txt" | Out-Null

Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices; using System.Collections.Generic;
public class QaWin {
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr p, EnumProc f, IntPtr l);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  // text of every visible dialog box (#32770) owned by one of the given processes
  public static List<string> Dialogs(uint[] pids) {
    var found = new List<string>();
    EnumWindows((h, l) => {
      uint pid; GetWindowThreadProcessId(h, out pid);
      if (Array.IndexOf(pids, pid) < 0 || !IsWindowVisible(h)) return true;
      var c = new StringBuilder(64); GetClassName(h, c, 64);
      if (c.ToString() != "#32770") return true;
      var t = new StringBuilder(512); GetWindowText(h, t, 512);
      var all = new StringBuilder("[" + pid + "] " + t);
      EnumChildWindows(h, (ch, l2) => { var s = new StringBuilder(1024); GetWindowText(ch, s, 1024); if (s.Length > 0) all.Append(" | " + s); return true; }, IntPtr.Zero);
      found.Add(all.ToString()); return true; }, IntPtr.Zero);
    return found;
  }
}
"@

if (Get-Process starter_x64 -ErrorAction SilentlyContinue) { "A game instance is already running; not touching it. RESULT: SKIP"; Stop-Transcript | Out-Null; exit 2 }
Get-ChildItem "$Game\out" -Filter "basic_network*.log" -ErrorAction SilentlyContinue | ForEach-Object { [IO.File]::Delete($_.FullName) }
Get-ChildItem "$Game\out" -Filter "mp_*.txt" -ErrorAction SilentlyContinue | ForEach-Object { [IO.File]::Delete($_.FullName) }
Copy-Item "$Game\_mp_research\test_battle_image.cfgpack" "$Game\data\common\shared\config\tacgame_image.cfgpack" -Force
$started = Get-Date
$dumpBefore = Get-Item "$Game\out\minidump.dmp" -ErrorAction SilentlyContinue
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$half = [int]($screen.Width / 2)
$mine = New-Object System.Collections.ArrayList   # every game process this run started

function Find-Battle([int[]]$except) {
    Get-CimInstance Win32_Process -Filter "Name='starter_x64.exe'" |
        Where-Object { $_.CommandLine -match 'tacgame\.progpack' -and $except -notcontains $_.ProcessId -and $_.ExecutablePath -like "$Game\*" } |
        Select-Object -First 1 | ForEach-Object { Get-Process -Id $_.ProcessId }
}
function Crash-Check([string]$when) {
    $pids = [uint32[]]@($mine | ForEach-Object { [uint32]$_.Id })
    $d = [QaWin]::Dialogs($pids)
    foreach ($x in $d) { Check "no error dialog ($when)" $false $x }
    $d.Count -eq 0
}
function Finish([int]$code) {
    foreach ($p in $mine) { $p.Refresh(); "pid $($p.Id): $(if ($p.HasExited) { "exited, code $($p.ExitCode)" } else { 'running' })" }
    if (-not $KeepRunning) { foreach ($p in @($mine)[($mine.Count - 1)..0]) { Stop-Game $p } }
    $dump = Get-Item "$Game\out\minidump.dmp" -ErrorAction SilentlyContinue
    if ($dump -and (-not $dumpBefore -or $dump.LastWriteTime -gt $started)) {
        Check "no crash dump written" $false $dump.LastWriteTime
        & $Py "$tools\crash_info.py" $dump.FullName 2>&1 | Select-Object -First 30
        Copy-Item $dump.FullName "$runDir\minidump.dmp"
    } else { Check "no crash dump written" $true }
    Get-WinEvent -FilterHashtable @{ LogName = 'Application'; Id = 1000; StartTime = $started } -ErrorAction SilentlyContinue |
        Where-Object { $_.Message -match 'starter_x64' } | ForEach-Object { Check "no Windows crash event" $false (($_.Message -split "`n")[0..6] -join ' ') }
    Get-ChildItem "$Game\out" -Filter "basic_network*.log" | Copy-Item -Destination $runDir
    Get-ChildItem "$Game\out" -Filter "common_engine.log" | Copy-Item -Destination $runDir
    "--- build-dependent features the mod switched off"
    Select-String -Path "$runDir\basic_network*.log" -Pattern 'unknown game build|could not be hooked|not hooked' | ForEach-Object { "  $($_.Filename): $($_.Line.Substring([Math]::Min(22, $_.Line.Length)))" } | Sort-Object -Unique
    Show-Results
    $fail = @($script:Results | Where-Object Result -eq FAIL).Count
    "RESULT: $(if ($fail -eq 0 -and $code -eq 0) { 'PASS' } else { 'FAIL' })  ($runDir)"
    Stop-Transcript | Out-Null
    exit $(if ($fail -eq 0 -and $code -eq 0) { 0 } else { 1 })
}

# ---- A: host
$a = Start-Game "root\programs\tacgame.progpack, data\common\shared\config\tacgame_image.cfgpack, users\profiles, cloud, *:*, 0, 1" (@{
    MP_ROLE = "host"; MP_WINDOW = "0,0,$half,$($screen.Height)" } + $Extra)
[void]$mine.Add($a)
$alog = Get-MpLog $a "tacgame"
$ok = [bool](Wait-Log $alog 'net: hosting battle on' 120)
Check "A: hosting the battle" $ok
if (-not $ok) { [void](Crash-Check "A start"); Finish 1 }
$line = Wait-Log $alog 'this player commands' 10
Check "A: its player commands the Soviets" ($line -match 'commands Soviets') $(if ($line) { $line.Substring(22) })

# ---- B: joins with mp_join.exe, which downloads the battle and starts the game
$env:MP_TEST = "1"; $env:MP_WINDOW = "$half,0,$half,$($screen.Height)"
foreach ($k in $Extra.Keys) { Set-Item "env:$k" $Extra[$k] }
$join = & "$Game\mp_join.exe" 127.0.0.1 $Side 2>&1 | Out-String
$env:MP_TEST = $null; $env:MP_WINDOW = $null
foreach ($k in $Extra.Keys) { Remove-Item "env:$k" -ErrorAction SilentlyContinue }
Check "B: mp_join received the battle" ($join -match 'Battle received') ($join.Trim() -replace '\s+', ' ')
$b = $null
for ($i = 0; $i -lt 40 -and -not $b; $i++) { $b = Find-Battle @($a.Id); if (-not $b) { Start-Sleep 1 } }
Check "B: battle started" ([bool]$b)
if (-not $b) { [void](Crash-Check "B start"); Finish 1 }
[void]$mine.Add($b)
$blog = Get-MpLog $b "tacgame"
$versus = $Side -eq "germans"
$want = if ($versus) { "Germans" } else { "Soviets" }
$line = Wait-Log $blog 'this player commands' 120
Check "B: its player commands the $want" ($line -match "commands $want") $(if ($line) { $line.Substring(22) })
Check "B: connected to A" ([bool](Wait-Log $blog 'net: connected to host' 120))
if (-not (Crash-Check "after join")) { Finish 1 }
if ($versus) {
    Check "A: versus, AI commander off" ([bool](Wait-Log $alog 'AI commander switched off' 20))
    Check "B: versus, AI commander off" ([bool](Wait-Log $blog 'AI commander switched off' 20))
}
Check "Start button is shared (A)" ([bool](Wait-Log $alog 'Start button shared' 30))
Check "Start button is shared (B)" ([bool](Wait-Log $blog 'Start button shared' 30))
Start-Sleep 3
Send-Ready $a
Check "A pressed Start: A waits for B" ([bool](Wait-Log $alog 'ready: this player has finished deployment, waiting' 10))
Start-Sleep 5
Check "deployment does not end on A's press alone" (-not (Select-String -Path $alog, $blog -Pattern 'phase: initial orders' -Quiet))
Send-Ready $b
Check "B pressed Start: A reaches the initial orders" ([bool](Wait-Log $alog 'phase: initial orders' 30))
Check "B pressed Start: B reaches the initial orders" ([bool](Wait-Log $blog 'phase: initial orders' 30))
Start-Sleep 3
Send-Ready $b
Check "B pressed Start: B waits for A" ([bool](Wait-Log $blog 'ready: this player has finished the initial orders, waiting' 10))
Start-Sleep 5
Check "the battle does not start on B's press alone" (-not (Select-String -Path $alog, $blog -Pattern 'phase: battle$' -Quiet))
Send-Ready $a
$aBattle = [bool](Wait-Log $alog 'phase: battle$' 30); $bBattle = [bool](Wait-Log $blog 'phase: battle$' 30)
if (-not $aBattle -or -not $bBattle) {
    # Start not shared on this build: push both players on so the combat part still gets tested
    Send-Ready $a; Send-Ready $b; Start-Sleep 3; Send-Ready $a; Send-Ready $b
    $aBattle = [bool](Wait-Log $alog 'phase: battle$' 30); $bBattle = [bool](Wait-Log $blog 'phase: battle$' 30)
}
Check "A: battle phase reached" $aBattle
Check "B: battle phase reached" $bBattle
if (-not (Crash-Check "battle start")) { Finish 1 }
for ($t = 0; $t -lt $Warmup; $t += 10) { Start-Sleep 10; if (-not (Crash-Check "fight")) { Finish 1 } }
[void](Save-Shot $a "versus_a")
[void](Save-Shot $b "versus_b")

"--- combat comparison, A against B"
$diff = & $Py "$tools\combat_diff.py" $a.Id $b.Id $Samples $Every 2>&1
$diff | Where-Object { $_ -match 'sample|disagree|worst|Traceback|Error|far ' }
$worst = if (($diff | Out-String) -match 'worst sample: (\d+)') { [int]$Matches[1] } else { 999 }
Check "units agree between the games (at most 5 disagreeing in the worst sample)" ($worst -le 5) "worst sample: $worst"
$far = @($diff | Select-String 'more than 5 m apart: (\d+)' | ForEach-Object { [int]$_.Matches[0].Groups[1].Value })
$farLast = if ($far.Count) { $far[-1] } else { 999 }
Check "every unit stands at the same place in both games (none more than 5 m apart in the last sample)" ($farLast -eq 0) "last sample: $farLast, all samples: $($far -join ' ')"
if ($versus) {
    $view = & $Py -I "$PSScriptRoot\fog_check.py" $tools $a.Id $b.Id 2>&1
    $view
    Check "fog of war: each game shows all its own units and hides some of the other player's" (($view | Out-String) -match 'fog: ok')
}
[void](Crash-Check "end")
foreach ($g in @($a, $b)) { $g.Refresh() }
Check "A: still running" (-not $a.HasExited)
Check "B: still running" (-not $b.HasExited)
if ($versus) {
    $asent = (Select-String -Path $alog -Pattern 'net: 5 s: sent ([0-9]+) and applied ([0-9]+)' | Select-Object -Last 6)
    $bsent = (Select-String -Path $blog -Pattern 'net: 5 s: sent ([0-9]+) and applied ([0-9]+)' | Select-Object -Last 6)
    $bout = ($bsent | ForEach-Object { [int]$_.Matches[0].Groups[1].Value } | Measure-Object -Sum).Sum
    $ain = ($asent | ForEach-Object { [int]$_.Matches[0].Groups[2].Value } | Measure-Object -Sum).Sum
    Check "B sends its own units, A applies them" ($bout -gt 0 -and $ain -gt 0) "B sent $bout, A applied $ain transforms in the last 30 s"
}
foreach ($pair in @(@("host", $alog), @("join", $blog))) {
    "--- $($pair[0])"
    (Select-String -Path $pair[1] -Pattern 'state: 5 s|net: 5 s|shots: 5 s').Line | Select-Object -Last 4 | ForEach-Object { $_.Substring([Math]::Min(22, $_.Length)) }
}
Finish 0
