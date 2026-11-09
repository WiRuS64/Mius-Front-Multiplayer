# A real fight between the two players, two games on one PC, no mouse or keyboard input. run_versus.ps1 leaves the
# forces kilometres apart (0 hits), so it says nothing about casualties. Here the joiner's force is brought within
# firing range during deployment, the battle runs, both games are compared, the battle is ended and the results of
# both games are looked at.
#   run_fight.ps1 -Tag fight [-Metres 200] [-Fight 180] [-Speed 1] [-KeepRunning]
param([string]$Game = "$env:USERPROFILE\Desktop\миус тесты", [string]$Tag = "fight", [double]$Metres = 200, [int]$Fight = 180,
      [double]$Speed = 1, [switch]$KeepRunning, [hashtable]$Extra = @{}, [string]$Image = "", [int]$MaxTime = 0)
$ErrorActionPreference = "Continue"
$Game = (Resolve-Path $Game).Path
$Py = "D:\programs\Python312\python.exe"
. "$Game\_mp_research\tools\auto.ps1"
$script:Game = $Game
$tools = "$Game\_mp_research\tools"
$runDir = "$PSScriptRoot\runs\$Tag-$(Get-Date -Format yyyyMMdd-HHmmss)"
New-Item -ItemType Directory -Force $runDir | Out-Null
$script:Shots = $runDir
Start-Transcript -Path "$runDir\transcript.txt" | Out-Null
if (Get-Process starter_x64 -ErrorAction SilentlyContinue) { "A game instance is already running; not touching it. RESULT: SKIP"; Stop-Transcript | Out-Null; exit 2 }
Get-ChildItem "$Game\out","$Game\mp_logs" -Filter "basic_network*.log" -ErrorAction SilentlyContinue | ForEach-Object { [IO.File]::Delete($_.FullName) }
Copy-Item $(if ($Image) { $Image } else { "$Game\_mp_research\test_battle_image.cfgpack" }) "$Game\data\common\shared\config\tacgame_image.cfgpack" -Force
$started = Get-Date
$dumpBefore = Get-Item "$Game\out\minidump.dmp" -ErrorAction SilentlyContinue
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$half = [int]($screen.Width / 2)
$vars = @{ MP_TEST_SPEED = "$Speed" } + $Extra
if ($MaxTime -gt 0) { $vars["MP_TEST_MAXTIME"] = "$MaxTime" }
$mine = New-Object System.Collections.ArrayList

function Done {
    if (-not $KeepRunning) {
        # a battle that ends starts the game's menu program; those children are this run's too (by parent id, in this folder)
        $ids = @($mine | ForEach-Object { $_.Id })
        foreach ($p in @($mine)) { Stop-Game $p }
        Start-Sleep 2
        Get-CimInstance Win32_Process -Filter "Name='starter_x64.exe'" | Where-Object { $ids -contains $_.ParentProcessId -and $_.ExecutablePath -like "$Game\*" } |
            ForEach-Object { Stop-Game (Get-Process -Id $_.ProcessId) }
    }
    $d = Get-Item "$Game\out\minidump.dmp" -ErrorAction SilentlyContinue
    Check "no crash dump" (-not ($d -and (-not $dumpBefore -or $d.LastWriteTime -gt $started)))
    Get-WinEvent -FilterHashtable @{ LogName = 'Application'; Id = 1000; StartTime = $started } -ErrorAction SilentlyContinue |
        Where-Object { $_.Message -match 'starter_x64' } | ForEach-Object { Check "no Windows crash event" $false (($_.Message -split "`n")[0..6] -join ' ') }
    Get-ChildItem "$Game\out","$Game\mp_logs" -Filter "basic_network*.log" | Copy-Item -Destination $runDir
    Show-Results
    $fail = @($script:Results | Where-Object Result -eq FAIL).Count
    "RESULT: $(if ($fail -eq 0) { 'PASS' } else { 'FAIL' })  ($runDir)"
    Stop-Transcript | Out-Null
    exit $(if ($fail -eq 0) { 0 } else { 1 })
}

$a = Start-Game "root\programs\tacgame.progpack, data\common\shared\config\tacgame_image.cfgpack, users\profiles, cloud, *:*, 0, 1" (@{
    MP_ROLE = "host"; MP_WINDOW = "0,0,$half,$($screen.Height)" } + $vars)
[void]$mine.Add($a)
$alog = Get-MpLog $a "tacgame"
Check "A: hosting the battle" ([bool](Wait-Log $alog 'net: hosting battle on' 120))
$env:MP_TEST = "1"; $env:MP_WINDOW = "$half,0,$half,$($screen.Height)"
foreach ($k in $vars.Keys) { Set-Item "env:$k" $vars[$k] }
$join = & "$Game\mp_join.exe" 127.0.0.1 germans 2>&1 | Out-String
$env:MP_TEST = $null; $env:MP_WINDOW = $null
foreach ($k in $vars.Keys) { Remove-Item "env:$k" -ErrorAction SilentlyContinue }
$b = $null
for ($i = 0; $i -lt 40 -and -not $b; $i++) {
    $b = Get-CimInstance Win32_Process -Filter "Name='starter_x64.exe'" | Where-Object { $_.CommandLine -match 'tacgame\.progpack' -and $_.ProcessId -ne $a.Id } |
         Select-Object -First 1 | ForEach-Object { Get-Process -Id $_.ProcessId }
    if (-not $b) { Start-Sleep 1 }
}
Check "B: battle started" ([bool]$b) ($join.Trim() -replace '\s+', ' ')
if (-not $b) { Done }
[void]$mine.Add($b)
$blog = Get-MpLog $b "tacgame"
Check "B: connected" ([bool](Wait-Log $blog 'net: connected to host' 120))
Check "versus, AI commanders off" ([bool](Wait-Log $alog 'AI commander switched off' 20) -and [bool](Wait-Log $blog 'AI commander switched off' 20))
Check "Start button shared" ([bool](Wait-Log $alog 'Start button shared' 30) -and [bool](Wait-Log $blog 'Start button shared' 30))
Start-Sleep 3
$moved = & $Py -I "$PSScriptRoot\close_combat.py" $tools $b.Id $Metres 2>&1
$moved
Check "forces brought within firing range" (($moved | Out-String) -match 'close: \d+ joiner units moved')
Start-Sleep 3
Send-Ready $a; Send-Ready $b
Check "initial orders reached" ([bool](Wait-Log $alog 'phase: initial orders' 30) -and [bool](Wait-Log $blog 'phase: initial orders' 30))
Start-Sleep 3
Send-Ready $a; Send-Ready $b
Check "battle reached" ([bool](Wait-Log $alog 'phase: battle$' 30) -and [bool](Wait-Log $blog 'phase: battle$' 30))

for ($t = 0; $t -lt $Fight; $t += 30) {
    Start-Sleep 30
    foreach ($g in @($a, $b)) { $g.Refresh() }
    if ($a.HasExited -or $b.HasExited) { Check "both games alive during the fight" $false "after $t s"; Done }
    "--- +$($t + 30) s"
    & $Py -I "$PSScriptRoot\stat_probe.py" $tools $a.Id $b.Id 2>&1 | Select-Object -Last 2
    foreach ($log in @($alog, $blog)) { (Select-String -Path $log -Pattern 'hit: 5 s').Line | Select-Object -Last 1 | ForEach-Object { $_.Substring(22, [Math]::Min(150, $_.Length - 22)) } }
}
[void](Save-Shot $a "fight_a"); [void](Save-Shot $b "fight_b")
# the fight is often only starting at this point: this says whether the comparison below saw any of it
$hitsNow = @(Select-String -Path $alog,$blog -Pattern 'hit: 5 s: [1-9]').Count
Check "there was fighting before the comparison" ($hitsNow -gt 0) "$hitsNow five-second reports with hits"
$diff = & $Py "$tools\combat_diff.py" $a.Id $b.Id 4 10 2>&1
$diff | Where-Object { $_ -match 'sample|disagree|worst|Traceback' }
$diff | Set-Content "$runDir\combat_diff.txt"
$worst = if (($diff | Out-String) -match 'worst sample: (\d+)') { [int]$Matches[1] } else { 999 }
Check "units agree in a real fight (at most 5 disagreeing)" ($worst -le 5) "worst sample: $worst"
$far = @($diff | Select-String 'more than 5 m apart: (\d+)' | ForEach-Object { [int]$_.Matches[0].Groups[1].Value })
Check "no unit more than 5 m apart" ($far.Count -gt 0 -and $far[-1] -eq 0) "all samples: $($far -join ' ')"
"--- statistics before the end"
& $Py -I "$PSScriptRoot\stat_probe.py" $tools $a.Id $b.Id 2>&1 | Out-File "$runDir\stat_before_end.txt" -Encoding utf8
Get-Content "$runDir\stat_before_end.txt" -Tail 3
"--- ending the battle"
& $Py -I "$PSScriptRoot\stat_probe.py" $tools $a.Id $b.Id 2>&1 | Out-File "$runDir\stat_final.txt" -Encoding utf8
if ($MaxTime -gt 0) {
    Check "A: the battle ran out and is over" ([bool](Wait-Log $alog 'end: the battle is over here|end: the battle has run out here' ($MaxTime + 180))) ""
    Check "B: told the battle is over" ([bool](Wait-Log $blog "end: the host's battle is over" 60)) ""
    Start-Sleep 6
    [void](Save-Shot $a "result_a"); [void](Save-Shot $b "result_b")
    Start-Sleep 4
    [void](Save-Shot $a "result2_a"); [void](Save-Shot $b "result2_b")
} else {
    Send-Resign $a
    Check "A: battle program ended on resign" ([bool](Wait-Log $alog 'end: |destroy' 30))
}
$hits = @(Select-String -Path $alog,$blog -Pattern 'hit: 5 s: [1-9]').Count
Check "there was fighting (hits in the logs, whole battle)" ($hits -gt 0) "$hits five-second reports with hits"
foreach ($log in @($alog, $blog)) { (Select-String -Path $log -Pattern 'end: ').Line | Select-Object -Last 8 | ForEach-Object { $_.Substring(13, [Math]::Min(170, $_.Length - 13)) } }
Done
