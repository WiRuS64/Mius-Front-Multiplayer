# The whole automated suite in a row, one game pair at a time; prints each run's checks and a summary.
#   run_suite.ps1 -Tag 262 [-Only fight,versus]
param([string]$Tag = "suite", [string[]]$Only = @())
$runs = @(
    @{ Name = "shift"; Script = "run_fight.ps1"; Args = @{ Fight = 240; ShiftGroups = 8192 } },
    @{ Name = "fight"; Script = "run_fight.ps1"; Args = @{ Fight = 360 } },
    @{ Name = "versus"; Script = "run_versus.ps1"; Args = @{} },
    @{ Name = "op"; Script = "run_operation.ps1"; Args = @{} },
    @{ Name = "hang"; Script = "run_turnhang.ps1"; Args = @{} }
)
$summary = @()
foreach ($r in $runs) {
    if ($Only.Count -and $Only -notcontains $r.Name) { continue }
    "=========== $($r.Name)$Tag"
    $cmd = "& '$PSScriptRoot\$($r.Script)' -Tag $($r.Name)$Tag" + (($r.Args.GetEnumerator() | ForEach-Object { " -$($_.Key) $($_.Value)" }) -join '')
    $out = & powershell -NoProfile -ExecutionPolicy Bypass -Command $cmd 2>&1 | ForEach-Object { "$_" }
    $out | Where-Object { $_ -match '^(PASS|FAIL)|RESULT|foreign:|^  \d+: ' }
    $summary += "$($r.Name)$Tag  " + (($out | Where-Object { $_ -match 'RESULT' } | Select-Object -Last 1) -replace '\s+\(.*', '')
    Get-CimInstance Win32_Process -Filter "Name='starter_x64.exe'" | Where-Object { $_.ExecutablePath -like "*\Desktop\миус тесты\*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Start-Sleep 3
}
"=========== summary"
$summary
